from __future__ import annotations
import os
import sqlite3
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from auto_review.vcs.base import ReviewComment


class FeedbackStore:
    """
    SQLite-backed memory store for tracking review comments, developer feedback,
    and powering Recursive Self-Improvement (RSI) feedback loops.
    """

    def __init__(self, db_path: str = ".auto_review/memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS review_comments (
                    comment_id TEXT PRIMARY KEY,
                    target_id TEXT,
                    vcs_type TEXT,
                    file_path TEXT,
                    line_number INTEGER,
                    severity TEXT,
                    category TEXT,
                    title TEXT,
                    comment TEXT,
                    suggestion TEXT,
                    confidence INTEGER,
                    status TEXT DEFAULT 'PENDING',  -- PENDING, ACCEPTED, DISMISSED, FALSE_POSITIVE
                    developer_notes TEXT DEFAULT '',
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meta_evals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_timestamp TEXT,
                    total_comments INTEGER,
                    accepted_count INTEGER,
                    dismissed_count INTEGER,
                    precision_rate REAL
                )
            """)
            conn.commit()

    @staticmethod
    def generate_comment_id(file_path: str, line_number: int, title: str) -> str:
        key = f"{file_path}:{line_number}:{title.strip().lower()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]

    def save_comments(self, vcs_type: str, target_id: str, comments: List[ReviewComment]):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            for c in comments:
                cid = c.comment_id or self.generate_comment_id(c.file_path, c.line_number, c.title)
                c.comment_id = cid
                conn.execute("""
                    INSERT OR IGNORE INTO review_comments (
                        comment_id, target_id, vcs_type, file_path, line_number,
                        severity, category, title, comment, suggestion, confidence, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
                """, (
                    cid, target_id, vcs_type, c.file_path, c.line_number,
                    c.severity.value, c.category.value, c.title, c.comment,
                    c.suggestion or "", c.confidence, now
                ))
            conn.commit()

    def record_feedback(self, comment_id: str, status: str, developer_notes: str = "") -> bool:
        """Records developer response: 'ACCEPTED', 'DISMISSED', or 'FALSE_POSITIVE'."""
        normalized_status = status.upper().strip()
        if normalized_status not in ("ACCEPTED", "DISMISSED", "FALSE_POSITIVE"):
            raise ValueError(f"Invalid status '{status}'. Must be ACCEPTED, DISMISSED, or FALSE_POSITIVE.")

        with self._get_conn() as conn:
            cur = conn.execute("""
                UPDATE review_comments
                SET status = ?, developer_notes = ?
                WHERE comment_id = ?
            """, (normalized_status, developer_notes, comment_id))
            conn.commit()
            return cur.rowcount > 0

    def get_pending_comments(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM review_comments WHERE status = 'PENDING'
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_negative_feedback(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns false positives and dismissed comments to synthesize negative constraints."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM review_comments
                WHERE status IN ('DISMISSED', 'FALSE_POSITIVE')
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_exemplars(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns accepted, high-value comments to serve as positive few-shots."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM review_comments
                WHERE status = 'ACCEPTED' AND confidence >= 8
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_metrics(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM review_comments").fetchone()[0]
            accepted = conn.execute("SELECT COUNT(*) FROM review_comments WHERE status = 'ACCEPTED'").fetchone()[0]
            dismissed = conn.execute("SELECT COUNT(*) FROM review_comments WHERE status IN ('DISMISSED', 'FALSE_POSITIVE')").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM review_comments WHERE status = 'PENDING'").fetchone()[0]
            evaluated = accepted + dismissed
            precision = (accepted / evaluated * 100) if evaluated > 0 else 0.0

            return {
                "total_generated": total,
                "accepted": accepted,
                "dismissed": dismissed,
                "pending": pending,
                "precision_rate": round(precision, 1)
            }
