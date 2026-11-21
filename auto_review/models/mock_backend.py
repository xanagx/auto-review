from __future__ import annotations
import json
from auto_review.models.base import ModelBackend


class MockBackend(ModelBackend):
    """Predictable mock backend for testing, dry-runs, and offline demonstrations."""

    def __init__(self, canned_findings: list | None = None):
        self.canned_findings = canned_findings

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        # If it's a Critic prompt
        if "Strict Code Review Verifier" in system_prompt or '"verdict": "KEEP"' in system_prompt:
            return json.dumps({
                "verdict": "KEEP",
                "reason": "Finding indicates genuine risk without being an annoying nitpick."
            })

        # If it's a Rule Synthesizer prompt
        if "Meta-Prompt Engineer" in system_prompt or "Synthesize a concise set" in user_prompt:
            return (
                "- Avoid flagging missing type annotations in test helpers.\n"
                "- Respect project convention of using sentinel values instead of exceptions in data parsers."
            )

        if self.canned_findings is not None:
            return json.dumps(self.canned_findings)

        # Default sample review finding
        return json.dumps([
            {
                "file": "sample.py",
                "line": 15,
                "severity": "WARNING",
                "category": "BUG",
                "title": "Potential Unhandled None / Nil Return",
                "comment": "The function returns None on cache miss, but caller accesses .id directly without null check.",
                "suggestion": "val = get_item()\nif not val:\n    return None",
                "confidence": 9
            }
        ])
