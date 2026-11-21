from __future__ import annotations
import os
import subprocess
from typing import Optional, List
from auto_review.vcs.base import AbstractVCSAdapter, ChangeSet, ReviewComment
from auto_review.core.parser import DiffParser


class GitAdapter(AbstractVCSAdapter):
    """Adapter for interacting with Git repositories."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)

    def _run_git(self, args: List[str]) -> str:
        res = subprocess.run(
            ["git"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(args)}\nError: {res.stderr.strip()}")
        return res.stdout

    def get_changeset(self, target: Optional[str] = None) -> ChangeSet:
        target_id = target or "working-copy"
        title = "Local Git changes"

        if target in ("staged", "--cached", "--staged"):
            raw_diff = self._run_git(["diff", "--cached"])
            title = "Staged Git changes"
        elif target in ("unstaged", "working", "workdir"):
            raw_diff = self._run_git(["diff"])
            title = "Unstaged Git changes"
        elif target and "..." in target:
            raw_diff = self._run_git(["diff", target])
            title = f"Git diff {target}"
        elif target:
            # Commit hash or ref
            try:
                raw_diff = self._run_git(["show", "--format=", target])
                title = self._run_git(["log", "-1", "--pretty=%B", target]).strip()
            except Exception:
                raw_diff = self._run_git(["diff", target])
        else:
            # Auto-detect: check staged first, then unstaged
            raw_diff = self._run_git(["diff", "--cached"])
            if raw_diff.strip():
                title = "Staged Git changes"
                target_id = "staged"
            else:
                raw_diff = self._run_git(["diff"])
                title = "Unstaged Git changes"
                target_id = "unstaged"

        # Extract author & branch if available
        author = ""
        try:
            author = self._run_git(["config", "user.name"]).strip()
        except Exception:
            pass

        files = DiffParser.parse(raw_diff)

        return ChangeSet(
            target_id=target_id,
            vcs_type="git",
            title=title,
            author=author,
            files=files,
            raw_diff=raw_diff,
            metadata={"repo_path": self.repo_path}
        )

    def get_file_content(self, path: str, revision: Optional[str] = None) -> Optional[str]:
        full_path = os.path.join(self.repo_path, path)
        if revision:
            try:
                return self._run_git(["show", f"{revision}:{path}"])
            except Exception:
                pass
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception:
                return None
        return None

    def post_comments(self, changeset: ChangeSet, comments: List[ReviewComment]) -> bool:
        # In CLI mode, comments are primarily reported to stdout or saved as review artifacts.
        # Future GitHub API / GitLab API posting can be wired here.
        return True
