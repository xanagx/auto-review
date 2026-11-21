import pytest
from auto_review.vcs.p4_adapter import P4Adapter
from auto_review.vcs.base import ReviewComment, Severity, Category


P4_DESCRIBE_OUTPUT = """Change 89234 by john_doe@workspace on 2026/11/21 18:22:10 *pending*

    Refactor connection pooling logic.
    Prevent thread starvation under high load.

Shelved files ...
... //depot/src/pool.go#2 edit

Differences ...
==== //depot/src/pool.go#2 (text) ====
@@ -20,4 +20,6 @@
+    mu.Lock()
+    defer mu.Unlock()
"""


def test_parse_describe_output():
    adapter = P4Adapter()
    title, author, raw_diff = adapter._parse_describe_output(P4_DESCRIBE_OUTPUT, "89234")

    assert author == "john_doe"
    assert "Refactor connection pooling logic." in title
    assert "Prevent thread starvation" in title
    assert "==== //depot/src/pool.go#2" in raw_diff
    assert "mu.Lock()" in raw_diff


def test_format_swarm_comment_payload():
    adapter = P4Adapter(swarm_url="https://swarm.corp.internal")
    comment = ReviewComment(
        file_path="//depot/src/pool.go",
        line_number=21,
        severity=Severity.BLOCKER,
        category=Category.BUG,
        title="Deadlock Risk",
        comment="Lock acquired without defer inside early return loop.",
        suggestion="defer mu.Unlock()",
        confidence=9
    )

    payload = adapter.format_swarm_comment_payload("89234", comment)
    assert payload["topic"] == "reviews/89234"
    assert "[AI Review - BLOCKER] Deadlock Risk" in payload["body"]
    assert "suggested fix" in payload["body"].lower()
    assert payload["context"]["file"] == "//depot/src/pool.go"
    assert payload["context"]["rightLine"] == 21
