from __future__ import annotations
import os
import re
from typing import List, Dict, Any
from auto_review.models.base import ModelBackend
from auto_review.rsi.feedback_store import FeedbackStore


class RuleSynthesizer:
    """
    Synthesizes project-specific guidelines from developer feedback (RSI loop).
    Converts rejected/dismissed comments into distilled negative constraints.
    """

    SYNTHESIZER_SYSTEM = """You are a Machine Learning Meta-Prompt Engineer.
Your task is to analyze developer feedback on AI code review comments, particularly comments that were REJECTED, DISMISSED, or marked as FALSE POSITIVES by developers.

Based on these rejections and developer notes, extract 3 to 7 concise, highly actionable project guidelines that instruct future AI reviews on what NOT to flag or what specific patterns to respect.

Rules for guidelines:
- Be specific, actionable, and succinct.
- State clearly what should NOT be commented on.
- Focus on codebase idioms, acceptable conventions, and anti-patterns to avoid flagging.
- Format as Markdown bullet points under appropriate headings.
"""

    def __init__(self, backend: ModelBackend, store: FeedbackStore, guidelines_path: str = ".auto_review/guidelines.md"):
        self.backend = backend
        self.store = store
        self.guidelines_path = guidelines_path

    def optimize_guidelines(self) -> str:
        negatives = self.store.get_negative_feedback(limit=50)
        exemplars = self.store.get_exemplars(limit=10)

        if not negatives and not exemplars:
            return "No feedback records found yet in memory database. Run reviews and record feedback first."

        # Format feedback items
        neg_text = []
        for item in negatives:
            neg_text.append(
                f"- File: {item['file_path']}, Title: '{item['title']}'\n"
                f"  Comment: {item['comment'][:200]}\n"
                f"  Dev Feedback/Reason: {item['developer_notes'] or 'Dismissed by engineer'}"
            )

        pos_text = []
        for item in exemplars:
            pos_text.append(
                f"- File: {item['file_path']}, Title: '{item['title']}'\n"
                f"  Comment: {item['comment'][:200]}"
            )

        user_prompt = f"""### Dismissed / False-Positive Comments ({len(negatives)} items):
{chr(10).join(neg_text) if neg_text else 'None yet.'}

### Highly Rated / Accepted Comments ({len(exemplars)} items):
{chr(10).join(pos_text) if pos_text else 'None yet.'}

Synthesize a concise set of project guidelines for this repository so future AI reviews avoid repeating the dismissed mistakes and emulate accepted high-signal patterns."""

        new_guidelines = self.backend.generate(self.SYNTHESIZER_SYSTEM, user_prompt, temperature=0.2)

        header = (
            "# Repository AI Review Guidelines (RSI Auto-Synthesized)\n"
            "# Generated automatically from developer feedback loops.\n\n"
        )
        content = header + new_guidelines.strip() + "\n"

        os.makedirs(os.path.dirname(os.path.abspath(self.guidelines_path)), exist_ok=True)
        with open(self.guidelines_path, "w", encoding="utf-8") as f:
            f.write(content)

        return content

    def load_active_guidelines(self) -> str:
        if os.path.exists(self.guidelines_path):
            try:
                with open(self.guidelines_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return ""
