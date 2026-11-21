import os
import tempfile
import pytest
from auto_review.rsi.feedback_store import FeedbackStore
from auto_review.rsi.rule_synthesizer import RuleSynthesizer
from auto_review.models.mock_backend import MockBackend
from auto_review.vcs.base import ReviewComment, Severity, Category


def test_feedback_store_and_metrics():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        store = FeedbackStore(db_path=db_path)

        c1 = ReviewComment(
            file_path="foo.py",
            line_number=10,
            severity=Severity.BLOCKER,
            category=Category.BUG,
            title="Unchecked null pointer",
            comment="Value could be null",
            confidence=9
        )
        c2 = ReviewComment(
            file_path="bar.py",
            line_number=25,
            severity=Severity.SUGGESTION,
            category=Category.DESIGN,
            title="Style preference",
            comment="Prefer list comprehension",
            confidence=7
        )

        store.save_comments("git", "commit-123", [c1, c2])

        pending = store.get_pending_comments()
        assert len(pending) == 2

        # Record acceptance of c1, rejection of c2
        assert store.record_feedback(c1.comment_id, "ACCEPTED", "Great catch")
        assert store.record_feedback(c2.comment_id, "FALSE_POSITIVE", "Standard loop preferred here")

        metrics = store.get_metrics()
        assert metrics["total_generated"] == 2
        assert metrics["accepted"] == 1
        assert metrics["dismissed"] == 1
        assert metrics["pending"] == 0
        assert metrics["precision_rate"] == 50.0

        exemplars = store.get_exemplars()
        assert len(exemplars) == 1
        assert exemplars[0]["comment_id"] == c1.comment_id

        negatives = store.get_negative_feedback()
        assert len(negatives) == 1
        assert negatives[0]["comment_id"] == c2.comment_id


def test_rule_synthesizer():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        guidelines_path = os.path.join(tmpdir, "guidelines.md")

        store = FeedbackStore(db_path=db_path)
        c = ReviewComment(
            file_path="test_api.py",
            line_number=5,
            severity=Severity.NITPICK,
            category=Category.DOCS,
            title="Missing docstring",
            comment="Add docstring to test helper",
            confidence=8
        )
        store.save_comments("p4", "cl-999", [c])
        store.record_feedback(c.comment_id, "FALSE_POSITIVE", "Do not require docstrings in tests")

        backend = MockBackend()
        synthesizer = RuleSynthesizer(backend=backend, store=store, guidelines_path=guidelines_path)

        res = synthesizer.optimize_guidelines()
        assert os.path.exists(guidelines_path)
        active = synthesizer.load_active_guidelines()
        assert "Guidelines" in active or "Avoid" in active
