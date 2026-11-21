from __future__ import annotations
import re
from typing import List, Optional
from auto_review.vcs.base import FileDiff, Hunk


class DiffParser:
    """Parses unified diff outputs from both Git and Perforce."""

    GIT_DIFF_HEADER = re.compile(r"^diff --git (?:a/)?(\S+) (?:b/)?(\S+)")
    P4_DIFF_HEADER = re.compile(r"^====\s+(.+?)(?:#\d+)?\s+(?:\([^\)]+\)\s+)?====")
    HUNK_HEADER = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

    @classmethod
    def parse(cls, raw_diff: str) -> List[FileDiff]:
        files: List[FileDiff] = []
        current_file: Optional[FileDiff] = None
        current_hunk: Optional[Hunk] = None
        current_new_line = 0

        lines = raw_diff.splitlines()
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            # 1. Check for Git file header
            git_match = cls.GIT_DIFF_HEADER.match(line)
            if git_match:
                if current_file:
                    files.append(current_file)
                old_path = git_match.group(1).lstrip("a/")
                new_path = git_match.group(2).lstrip("b/")
                current_file = FileDiff(path=new_path, old_path=old_path, hunks=[], raw_diff=line + "\n")
                current_hunk = None
                i += 1
                continue

            # 2. Check for P4 file header: ==== //depot/path/file#rev (text) ====
            p4_match = cls.P4_DIFF_HEADER.match(line)
            if p4_match:
                if current_file:
                    files.append(current_file)
                p4_path = p4_match.group(1).strip()
                # Clean depot syntax if desirable, but keep path intact
                current_file = FileDiff(path=p4_path, old_path=p4_path, hunks=[], raw_diff=line + "\n")
                current_hunk = None
                i += 1
                continue

            # 3. Check for Hunk header: @@ -old,count +new,count @@
            hunk_match = cls.HUNK_HEADER.match(line)
            if hunk_match and current_file:
                old_start = int(hunk_match.group(1))
                old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                new_start = int(hunk_match.group(3))
                new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1

                current_hunk = Hunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=[line]
                )
                current_file.hunks.append(current_hunk)
                current_file.raw_diff += line + "\n"
                current_new_line = new_start
                i += 1
                continue

            # 4. Hunk content lines
            if current_hunk and current_file:
                current_file.raw_diff += line + "\n"
                current_hunk.lines.append(line)

                if line.startswith("+") and not line.startswith("+++"):
                    current_file.added_lines.append(current_new_line)
                    current_new_line += 1
                elif line.startswith("-") and not line.startswith("---"):
                    pass  # Old file line removed; new file line counter does not increment
                else:
                    # Context line
                    current_new_line += 1
                i += 1
                continue

            # Accumulate headers / metadata into current file raw_diff if present
            if current_file:
                current_file.raw_diff += line + "\n"

            i += 1

        if current_file:
            files.append(current_file)

        return files
