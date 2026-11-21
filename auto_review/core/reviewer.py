from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Optional
from auto_review.models.base import ModelBackend
from auto_review.vcs.base import ChangeSet, ReviewComment, Severity, Category, AbstractVCSAdapter
from auto_review.core.prompts import SYSTEM_REVIEW_PROMPT, build_review_user_prompt
from auto_review.rsi.critic import MetaCritic
from auto_review.rsi.feedback_store import FeedbackStore
from auto_review.rsi.rule_synthesizer import RuleSynthesizer


class CodeReviewer:
    """
    Core review orchestrator.
    Implements multi-pass generation, RSI self-criticism, and guideline learning.
    """

    def __init__(
        self,
        backend: ModelBackend,
        store: Optional[FeedbackStore] = None,
        enable_critic: bool = True,
        min_confidence: int = 7,
    ):
        self.backend = backend
        self.store = store or FeedbackStore()
        self.synthesizer = RuleSynthesizer(backend=self.backend, store=self.store)
        self.enable_critic = enable_critic
        self.min_confidence = min_confidence
        self.critic = MetaCritic(backend=self.backend)

    def review(self, changeset: ChangeSet, adapter: Optional[AbstractVCSAdapter] = None) -> List[ReviewComment]:
        if not changeset.raw_diff.strip():
            return []

        # 1. Retrieve RSI guidelines & positive exemplars
        active_guidelines = self.synthesizer.load_active_guidelines()
        exemplars = self.store.get_exemplars(limit=3)

        # 2. Gather whole-file contexts if adapter is supplied
        file_contexts: Dict[str, str] = {}
        if adapter:
            for f in changeset.files:
                content = adapter.get_file_content(f.path)
                if content:
                    file_contexts[f.path] = content

        # 3. Phase 1: Draft Review Comments (High-Recall Generation)
        user_prompt = build_review_user_prompt(
            vcs_type=changeset.vcs_type,
            target_id=changeset.target_id,
            title=changeset.title,
            author=changeset.author,
            raw_diff=changeset.raw_diff,
            active_guidelines=active_guidelines,
            exemplars=exemplars
        )

        resp_text = self.backend.generate(SYSTEM_REVIEW_PROMPT, user_prompt, temperature=0.15)
        raw_findings = self._parse_findings_json(resp_text)

        # Convert to ReviewComment objects
        candidate_comments: List[ReviewComment] = []
        for item in raw_findings:
            try:
                conf = int(item.get("confidence", 7))
                if conf < self.min_confidence:
                    continue

                sev_str = str(item.get("severity", "WARNING")).upper()
                sev = Severity(sev_str) if sev_str in Severity.__members__ else Severity.WARNING

                cat_str = str(item.get("category", "BUG")).upper()
                cat = Category(cat_str) if cat_str in Category.__members__ else Category.BUG

                file_path = str(item.get("file", ""))
                line_no = int(item.get("line", 0))

                c = ReviewComment(
                    file_path=file_path,
                    line_number=line_no,
                    severity=sev,
                    category=cat,
                    title=str(item.get("title", "Review Finding")).strip(),
                    comment=str(item.get("comment", "")).strip(),
                    suggestion=item.get("suggestion"),
                    confidence=conf
                )
                candidate_comments.append(c)
            except Exception:
                continue

        # 4. Phase 2: Adversarial Critic Verification Pass (RSI Self-Correction)
        if self.enable_critic and candidate_comments:
            verified_comments, discarded = self.critic.filter_comments(
                comments=candidate_comments,
                raw_diff=changeset.raw_diff,
                file_contexts=file_contexts
            )
        else:
            verified_comments = candidate_comments

        # 5. Persist to RSI memory store
        if verified_comments:
            self.store.save_comments(changeset.vcs_type, changeset.target_id, verified_comments)

        return verified_comments

    @staticmethod
    def _parse_findings_json(text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        # Find JSON array using regex
        match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        # Empty array
        if re.search(r"\[\s*\]", text):
            return []

        try:
            val = json.loads(text)
            if isinstance(val, list):
                return val
        except Exception:
            pass

        return []
