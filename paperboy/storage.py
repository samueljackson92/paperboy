"""Persistent storage for paper read/unread state using SQLite."""
from __future__ import annotations

import sqlite3
from pathlib import Path


DATA_DIR = Path.home() / ".local" / "share" / "paperboy"


class ReadStateStore:
    """Persists paper read/unread state in a local SQLite database.

    SQLite chosen over JSON for atomic updates, concurrent safety, and
    O(1) lookups without loading the full dataset into memory.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or (DATA_DIR / "state.db")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS read_state "
            "(paper_id TEXT PRIMARY KEY, is_read INTEGER NOT NULL DEFAULT 0)"
        )
        self._conn.commit()

    def is_read(self, paper_id: str) -> bool:
        """Return True if the paper has been marked read."""
        row = self._conn.execute(
            "SELECT is_read FROM read_state WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        return bool(row and row[0])

    def mark_read(self, paper_id: str) -> None:
        """Mark a paper as read."""
        self._conn.execute(
            "INSERT INTO read_state (paper_id, is_read) VALUES (?, 1) "
            "ON CONFLICT(paper_id) DO UPDATE SET is_read = 1",
            (paper_id,),
        )
        self._conn.commit()

    def mark_unread(self, paper_id: str) -> None:
        """Mark a paper as unread."""
        self._conn.execute(
            "INSERT INTO read_state (paper_id, is_read) VALUES (?, 0) "
            "ON CONFLICT(paper_id) DO UPDATE SET is_read = 0",
            (paper_id,),
        )
        self._conn.commit()

    def get_all_read_ids(self) -> set[str]:
        """Return all paper IDs currently marked as read."""
        rows = self._conn.execute(
            "SELECT paper_id FROM read_state WHERE is_read = 1"
        ).fetchall()
        return {r[0] for r in rows}

    def close(self) -> None:
        self._conn.close()
