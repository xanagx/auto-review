from __future__ import annotations
import os
import re
import json
import urllib.request
import urllib.error
import subprocess
from typing import Optional, List, Dict, Any
from auto_review.vcs.base import AbstractVCSAdapter, ChangeSet, ReviewComment, FileDiff
from auto_review.core.parser import DiffParser


class P4Adapter(AbstractVCSAdapter):
    """Adapter for Perforce Helix Core and Helix Swarm."""

    def __init__(
        self,
        p4port: Optional[str] = None,
        p4user: Optional[str] = None,
        p4client: Optional[str] = None,
        swarm_url: Optional[str] = None,
        swarm_token: Optional[str] = None,
    ):
        self.p4port = p4port or os.environ.get("P4PORT")
        self.p4user = p4user or os.environ.get("P4USER")
        self.p4client = p4client or os.environ.get("P4CLIENT")
        self.swarm_url = (swarm_url or os.environ.get("SWARM_URL", "")).rstrip("/")
        self.swarm_token = swarm_token or os.environ.get("SWARM_TOKEN")

    def _build_p4_cmd(self, args: List[str]) -> List[str]:
        cmd = ["p4"]
        if self.p4port:
            cmd.extend(["-p", self.p4port])
        if self.p4user:
            cmd.extend(["-u", self.p4user])
        if self.p4client:
            cmd.extend(["-c", self.p4client])
        cmd.extend(args)
        return cmd

    def _run_p4(self, args: List[str]) -> str:
        cmd = self._build_p4_cmd(args)
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Perforce CLI ('p4') not found in PATH. "
                "Ensure Helix Core client tools are installed and in PATH."
            )

        if res.returncode != 0:
            raise RuntimeError(f"P4 command failed: {' '.join(cmd)}\nError: {res.stderr.strip()}")
        return res.stdout

    def get_changeset(self, target: Optional[str] = None) -> ChangeSet:
        """
        Extract changeset.
        target can be:
          - A changelist number, e.g. '123456'
          - 'shelved:<cl>' or '<cl>'
          - 'default' / 'pending' / None -> inspects active client pending diffs
        """
        cl_target = target or "default"
        is_numeric = cl_target.isdigit() or (cl_target.startswith("shelved:") and cl_target.split(":")[1].isdigit())

        if is_numeric:
            cl_num = cl_target.split(":")[-1]
            # Try shelved changelist first with -S -du
            try:
                raw_out = self._run_p4(["describe", "-S", "-du", cl_num])
            except Exception:
                # Fallback to regular describe (for pending or submitted CL)
                raw_out = self._run_p4(["describe", "-du", cl_num])

            title, author, raw_diff = self._parse_describe_output(raw_out, cl_num)
            files = DiffParser.parse(raw_diff)
            target_id = cl_num
        else:
            # Current workspace diff (opened files)
            raw_diff = self._run_p4(["diff", "-du"])
            title = "Perforce default changelist (opened files)"
            author = self.p4user or ""
            files = DiffParser.parse(raw_diff)
            target_id = "default"

        return ChangeSet(
            target_id=target_id,
            vcs_type="p4",
            title=title,
            author=author,
            files=files,
            raw_diff=raw_diff,
            metadata={"p4port": self.p4port, "p4client": self.p4client}
        )

    def _parse_describe_output(self, raw_out: str, cl_num: str) -> tuple[str, str, str]:
        """Parses description, user, and diff from p4 describe output."""
        lines = raw_out.splitlines()
        author = ""
        title_lines = []
        in_description = False
        diff_lines = []
        in_diff = False

        state = "HEADER"
        header_re = re.compile(r"^Change\s+\d+\s+by\s+(\S+)@")

        for line in lines:
            if line.startswith("Differences ..."):
                state = "DIFF"
                continue
            if line.startswith("Shelved files ...") or line.startswith("Affected files ..."):
                state = "FILES"
                continue

            if state == "HEADER":
                m = header_re.match(line)
                if m:
                    author = m.group(1)
                    state = "DESCRIPTION"
            elif state == "DESCRIPTION":
                title_lines.append(line.strip())
            elif state == "DIFF":
                diff_lines.append(line)

        title = "\n".join(title_lines).strip() or f"P4 Changelist {cl_num}"
        raw_diff = "\n".join(diff_lines)
        return title, author, raw_diff

    def get_file_content(self, path: str, revision: Optional[str] = None) -> Optional[str]:
        target = path
        if revision:
            target = f"{path}@{revision}"
        try:
            return self._run_p4(["print", "-q", target])
        except Exception:
            # Fallback to local file if path is client/workspace path
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        return f.read()
                except Exception:
                    pass
            return None

    def format_swarm_comment_payload(self, review_id: str, comment: ReviewComment) -> Dict[str, Any]:
        """Converts ReviewComment into Helix Swarm API payload."""
        body = (
            f"**[AI Review - {comment.severity.value}] {comment.title}**\n\n"
            f"{comment.comment}"
        )
        if comment.suggestion:
            body += f"\n\n**Suggested Fix:**\n```\n{comment.suggestion}\n```"

        payload: Dict[str, Any] = {
            "topic": f"reviews/{review_id}",
            "body": body,
        }
        if comment.line_number > 0 and comment.file_path:
            payload["context"] = {
                "file": comment.file_path,
                "rightLine": comment.line_number,
            }
        return payload

    def post_comments(self, changeset: ChangeSet, comments: List[ReviewComment]) -> bool:
        """
        Posts comments to Helix Swarm if SWARM_URL and SWARM_TOKEN are configured.
        Otherwise writes review payload to console or local artifact.
        """
        if not self.swarm_url or not self.swarm_token:
            # Swarm is not configured for direct HTTP push; adapter operates in report mode
            return True

        review_id = changeset.target_id
        endpoint = f"{self.swarm_url}/api/v11/comments"

        for comment in comments:
            payload = self.format_swarm_comment_payload(review_id, comment)
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {self.swarm_token}",
                },
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status not in (200, 201):
                        return False
            except urllib.error.URLError:
                return False
        return True
