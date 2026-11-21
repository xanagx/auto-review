from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Tuple
from auto_review.models.base import ModelBackend
from auto_review.vcs.base import ReviewComment


class MetaCritic:
    """
    Adversarial Critic Pass for RSI.
    Filters out hallucinations, overly pedantic style nitpicks, and false positives.
    """

    CRITIC_SYSTEM_PROMPT = """You are a Principal Software Engineer acting as a Strict Code Review Verifier.
Your job is to critically scrutinize proposed AI review comments on code changes and DISCARD any that are:
1. Hallucinations or misreadings of the syntax/logic.
2. Minor style nitpicks, formatting, or personal preferences (leave these to linters).
3. Incorrect assumptions that are already handled elsewhere in the code.
4. Annoying, obvious, or low-value comments that would frustrate senior developers.

KEEP only comments that represent:
- Genuine logic bugs, edge case oversights, or null/concurrency crashes.
- Concrete security vulnerabilities.
- Significant performance regressions.
- Broken contracts or silent data corruption.

You must respond ONLY with a JSON object:
{
  "verdict": "KEEP" or "DISCARD",
  "reason": "Clear explanation of why this finding was verified or rejected"
}"""

    def __init__(self, backend: ModelBackend):
        self.backend = backend

    def filter_comments(
        self,
        comments: List[ReviewComment],
        raw_diff: str,
        file_contexts: Dict[str, str]
    ) -> Tuple[List[ReviewComment], List[Dict[str, Any]]]:
        """
        Runs critic evaluation on each comment.
        Returns: (verified_comments, discarded_records)
        """
        kept: List[ReviewComment] = []
        discarded: List[Dict[str, Any]] = []

        for c in comments:
            # Low confidence candidates automatically discarded
            if c.confidence < 7:
                discarded.append({
                    "comment": c,
                    "reason": f"Discarded due to low initial confidence score ({c.confidence} < 7)"
                })
                continue

            file_ctx = file_contexts.get(c.file_path, "")
            user_prompt = f"""Target File: {c.file_path}
Line Number: {c.line_number}
Category: {c.category.value}
Severity: {c.severity.value}

Proposed Comment Title: {c.title}
Proposed Comment Body: {c.comment}
Proposed Suggestion: {c.suggestion or 'None'}

Relevant Code Context (around line {c.line_number}):
{file_ctx[:3000] if file_ctx else '(Diff only)'}

Diff snippet:
{raw_diff[:3000]}

Should this comment be posted to the author? Output valid JSON with 'verdict' and 'reason'."""

            try:
                resp_text = self.backend.generate(self.CRITIC_SYSTEM_PROMPT, user_prompt, temperature=0.1)
                data = self._clean_json(resp_text)
                verdict = data.get("verdict", "KEEP").upper()
                reason = data.get("reason", "")

                if verdict == "KEEP":
                    kept.append(c)
                else:
                    discarded.append({"comment": c, "reason": reason})
            except Exception as e:
                # If critic call fails gracefully fall back to keeping if confidence >= 8
                if c.confidence >= 8:
                    kept.append(c)
                else:
                    discarded.append({"comment": c, "reason": f"Critic error: {e}"})

        return kept, discarded

    @staticmethod
    def _clean_json(text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
