from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class Severity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    SUGGESTION = "SUGGESTION"
    NITPICK = "NITPICK"


class Category(str, Enum):
    BUG = "BUG"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    DESIGN = "DESIGN"
    TESTING = "TESTING"
    DOCS = "DOCS"


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[str] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    old_path: Optional[str] = None
    status: str = "modified"  # added, modified, deleted, renamed
    hunks: List[Hunk] = field(default_factory=list)
    raw_diff: str = ""
    added_lines: List[int] = field(default_factory=list)  # 1-indexed line numbers in new file


@dataclass
class ChangeSet:
    target_id: str             # e.g., git commit hash, branch, or p4 changelist number
    vcs_type: str              # 'git' or 'p4'
    title: str                 # Commit message or CL description
    author: str = ""
    files: List[FileDiff] = field(default_factory=list)
    raw_diff: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewComment:
    file_path: str
    line_number: int           # Line in the updated file (or 0 for file-level)
    severity: Severity
    category: Category
    title: str
    comment: str
    suggestion: Optional[str] = None   # Proposed code replacement if applicable
    confidence: int = 10               # 1-10 scale
    comment_id: str = ""               # Deterministic hash for tracking in RSI memory

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "comment": self.comment,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
        }


class AbstractVCSAdapter(ABC):
    """Abstract interface to isolate VCS specifics (Git vs Perforce)."""

    @abstractmethod
    def get_changeset(self, target: Optional[str] = None) -> ChangeSet:
        """Extract diff and metadata for a given target commit/branch or changelist."""
        pass

    @abstractmethod
    def get_file_content(self, path: str, revision: Optional[str] = None) -> Optional[str]:
        """Fetch full content of a file for contextual code analysis."""
        pass

    @abstractmethod
    def post_comments(self, changeset: ChangeSet, comments: List[ReviewComment]) -> bool:
        """Publish review comments back to the VCS or code review platform."""
        pass
