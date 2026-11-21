import os
import tempfile
import pytest
from auto_review.core.reviewer import CodeReviewer
from auto_review.models.mock_backend import MockBackend
from auto_review.rsi.feedback_store import FeedbackStore
from auto_review.vcs.base import ChangeSet, FileDiff
from auto_review.core.formatter import OutputFormatter


def test_reviewer_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        store = FeedbackStore(db_path=db_path)

        canned = [
            {
                "file": "server.py",
                "line": 40,
                "severity": "BLOCKER",
                "category": "SECURITY",
                "title": "SQL Injection Vector",
                "comment": "Raw user input formatted directly into SQL query.",
                "suggestion": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
                "confidence": 10
            }
        ]
        backend = MockBackend(canned_findings=canned)
        reviewer = CodeReviewer(backend=backend, store=store, enable_critic=True)

        changeset = ChangeSet(
            target_id="feat/auth-update",
            vcs_type="git",
            title="Update authentication handler",
            author="alice",
            files=[FileDiff(path="server.py", added_lines=[40])],
            raw_diff="diff --git a/server.py b/server.py\n+ query = f'SELECT * FROM users WHERE id = {user_id}'\n"
        )

        comments = reviewer.review(changeset)
        assert len(comments) == 1
        c = comments[0]
        assert c.file_path == "server.py"
        assert c.line_number == 40
        assert c.severity.value == "BLOCKER"
        assert c.category.value == "SECURITY"

        # Check Output Formatters
        terminal_out = OutputFormatter.to_terminal(changeset, comments, use_color=False)
        assert "SQL Injection Vector" in terminal_out
        assert "Suggested Fix:" in terminal_out

        markdown_out = OutputFormatter.to_markdown(changeset, comments)
        assert "## 🤖 AI Auto-Review Findings" in markdown_out
        assert "```suggestion" in markdown_out

        json_out = OutputFormatter.to_json(changeset, comments)
        assert '"findings_count": 1' in json_out
