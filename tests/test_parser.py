import pytest
from auto_review.core.parser import DiffParser


GIT_SAMPLE_DIFF = """diff --git a/src/math.py b/src/math.py
index e69de29..49e19d7 100644
--- a/src/math.py
+++ b/src/math.py
@@ -10,4 +10,6 @@ def divide(a, b):
     existing_line()
-    return a / b
+    if b == 0:
+        raise ValueError("Division by zero")
+    return a / b
"""

P4_SAMPLE_DIFF = """==== //depot/project/main/service.py#3 (text) ====

@@ -5,5 +5,7 @@
 def connect():
-    return False
+    if retry_count > 3:
+        return None
+    return True
"""


def test_parse_git_diff():
    files = DiffParser.parse(GIT_SAMPLE_DIFF)
    assert len(files) == 1
    f = files[0]
    assert f.path == "src/math.py"
    assert len(f.hunks) == 1
    hunk = f.hunks[0]
    assert hunk.new_start == 10
    assert 11 in f.added_lines
    assert 12 in f.added_lines


def test_parse_p4_diff():
    files = DiffParser.parse(P4_SAMPLE_DIFF)
    assert len(files) == 1
    f = files[0]
    assert f.path == "//depot/project/main/service.py"
    assert len(f.hunks) == 1
    assert 6 in f.added_lines
    assert 7 in f.added_lines
