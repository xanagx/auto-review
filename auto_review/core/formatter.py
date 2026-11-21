from __future__ import annotations
import json
from typing import List, Dict, Any
from auto_review.vcs.base import ReviewComment, ChangeSet, Severity


class OutputFormatter:
    """Formats review results for terminal display, Markdown, or JSON."""

    # ANSI Colors
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    DIM = "\033[2m"

    @classmethod
    def to_terminal(cls, changeset: ChangeSet, comments: List[ReviewComment], use_color: bool = True) -> str:
        if not comments:
            msg = f"\n✓ No critical defects or risks identified for {changeset.vcs_type.upper()} target: {changeset.target_id}\n"
            return f"{cls.GREEN}{cls.BOLD}{msg}{cls.RESET}" if use_color else msg

        lines = []
        header = f"\n=== Auto-Review Report [{changeset.vcs_type.upper()}: {changeset.target_id}] ==="
        lines.append(f"{cls.BOLD}{cls.CYAN}{header}{cls.RESET}" if use_color else header)
        lines.append(f"Title: {changeset.title.splitlines()[0] if changeset.title else 'No description'}")
        lines.append(f"Total Findings: {len(comments)}\n")

        for i, c in enumerate(comments, 1):
            sev_color = cls.RED if c.severity == Severity.BLOCKER else (cls.YELLOW if c.severity == Severity.WARNING else cls.BLUE)
            prefix = f"[{c.severity.value}]"
            tag = f"{sev_color}{cls.BOLD}{prefix}{cls.RESET}" if use_color else prefix

            loc = f"{c.file_path}:{c.line_number}" if c.line_number > 0 else c.file_path
            loc_str = f"{cls.BOLD}{loc}{cls.RESET}" if use_color else loc

            lines.append(f"{i}. {tag} {c.title}")
            lines.append(f"   Location: {loc_str} (Category: {c.category.value}, Confidence: {c.confidence}/10, ID: {c.comment_id})")
            lines.append(f"   {c.comment}")

            if c.suggestion:
                sugg_header = "   Suggested Fix:"
                lines.append(f"{cls.GREEN}{sugg_header}{cls.RESET}" if use_color else sugg_header)
                for s_line in c.suggestion.strip().splitlines():
                    lines.append(f"     | {s_line}")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def to_markdown(cls, changeset: ChangeSet, comments: List[ReviewComment]) -> str:
        lines = []
        lines.append(f"## 🤖 AI Auto-Review Findings (`{changeset.vcs_type.upper()}: {changeset.target_id}`)")
        lines.append(f"**Target:** {changeset.target_id} | **Files Analyzed:** {len(changeset.files)}")
        lines.append("")

        if not comments:
            lines.append("✅ **No blocking defects or high-risk issues found.** Clean change!")
            return "\n".join(lines)

        lines.append("| Severity | Category | File | Line | Issue |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for c in comments:
            lines.append(f"| **{c.severity.value}** | {c.category.value} | `{c.file_path}` | {c.line_number or '-'} | {c.title} |")
        lines.append("")

        for i, c in enumerate(comments, 1):
            lines.append(f"### {i}. [{c.severity.value}] {c.title}")
            lines.append(f"- **File:** `{c.file_path}`")
            if c.line_number > 0:
                lines.append(f"- **Line:** `{c.line_number}`")
            lines.append(f"- **Category:** `{c.category.value}` | **Confidence:** `{c.confidence}/10` | **ID:** `{c.comment_id}`")
            lines.append("")
            lines.append(c.comment)
            lines.append("")
            if c.suggestion:
                lines.append("```suggestion")
                lines.append(c.suggestion.strip())
                lines.append("```")
                lines.append("")

        return "\n".join(lines)

    @classmethod
    def to_json(cls, changeset: ChangeSet, comments: List[ReviewComment]) -> str:
        payload = {
            "vcs_type": changeset.vcs_type,
            "target_id": changeset.target_id,
            "title": changeset.title,
            "findings_count": len(comments),
            "findings": [c.to_dict() for c in comments]
        }
        return json.dumps(payload, indent=2)

    @classmethod
    def to_swarm_comments(cls, changeset: ChangeSet, comments: List[ReviewComment]) -> List[Dict[str, Any]]:
        """Outputs list of Helix Swarm comment JSON bodies."""
        from auto_review.vcs.p4_adapter import P4Adapter
        adapter = P4Adapter()
        return [adapter.format_swarm_comment_payload(changeset.target_id, c) for c in comments]
