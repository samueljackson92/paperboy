"""Persistent storage for paper read/unread state using SQLite."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from paperboy.models import FilterState


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
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS bookmarks "
            "(paper_id TEXT PRIMARY KEY)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS saved_searches ("
            "name TEXT PRIMARY KEY, "
            "source TEXT NOT NULL DEFAULT 'All', "
            "keywords TEXT NOT NULL DEFAULT '', "
            "bookmarked_only INTEGER NOT NULL DEFAULT 0, "
            "sort_by TEXT NOT NULL DEFAULT 'date', "
            "sort_desc INTEGER NOT NULL DEFAULT 1"
            ")"
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
        rows = self._conn.execute(
            "SELECT paper_id FROM read_state WHERE is_read = 1"
        ).fetchall()
        return {r[0] for r in rows}

    def toggle_bookmark(self, paper_id: str) -> bool:
        """Toggle bookmark; returns the new state (True = bookmarked)."""
        exists = self._conn.execute(
            "SELECT 1 FROM bookmarks WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        if exists:
            self._conn.execute("DELETE FROM bookmarks WHERE paper_id = ?", (paper_id,))
            self._conn.commit()
            return False
        self._conn.execute("INSERT INTO bookmarks (paper_id) VALUES (?)", (paper_id,))
        self._conn.commit()
        return True

    def get_all_bookmarked_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT paper_id FROM bookmarks").fetchall()
        return {r[0] for r in rows}

    def save_search(self, name: str, state: FilterState) -> None:
        """Persist a named filter state."""
        self._conn.execute(
            "INSERT INTO saved_searches (name, source, keywords, bookmarked_only, sort_by, sort_desc) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET source=excluded.source, keywords=excluded.keywords, "
            "bookmarked_only=excluded.bookmarked_only, sort_by=excluded.sort_by, sort_desc=excluded.sort_desc",
            (name, state.source, state.keywords, int(state.bookmarked_only), state.sort_by, int(state.sort_desc)),
        )
        self._conn.commit()

    def get_saved_searches(self) -> list[tuple[str, FilterState]]:
        """Return all saved searches as (name, FilterState) pairs."""
        rows = self._conn.execute(
            "SELECT name, source, keywords, bookmarked_only, sort_by, sort_desc FROM saved_searches ORDER BY name"
        ).fetchall()
        return [
            (
                row[0],
                FilterState(
                    source=row[1],
                    keywords=row[2],
                    bookmarked_only=bool(row[3]),
                    sort_by=row[4],
                    sort_desc=bool(row[5]),
                ),
            )
            for row in rows
        ]

    def delete_search(self, name: str) -> None:
        self._conn.execute("DELETE FROM saved_searches WHERE name = ?", (name,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
