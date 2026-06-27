"""Tests for ReadStateStore persistence."""
from __future__ import annotations

from pathlib import Path

import pytest

from research_feed.storage import ReadStateStore


@pytest.fixture
def store(tmp_path: Path) -> ReadStateStore:
    return ReadStateStore(db_path=tmp_path / "test_state.db")


def test_initially_unread(store: ReadStateStore) -> None:
    assert store.is_read("paper:001") is False


def test_mark_read(store: ReadStateStore) -> None:
    store.mark_read("paper:001")
    assert store.is_read("paper:001") is True


def test_mark_unread(store: ReadStateStore) -> None:
    store.mark_read("paper:001")
    store.mark_unread("paper:001")
    assert store.is_read("paper:001") is False


def test_get_all_read_ids(store: ReadStateStore) -> None:
    store.mark_read("paper:001")
    store.mark_read("paper:002")
    store.mark_unread("paper:001")
    ids = store.get_all_read_ids()
    assert "paper:002" in ids
    assert "paper:001" not in ids


def test_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "persist.db"
    s1 = ReadStateStore(db_path=db)
    s1.mark_read("paper:abc")
    s1.close()
    s2 = ReadStateStore(db_path=db)
    assert s2.is_read("paper:abc") is True
    s2.close()


def test_idempotent_mark_read(store: ReadStateStore) -> None:
    store.mark_read("paper:001")
    store.mark_read("paper:001")
    assert store.is_read("paper:001") is True


def test_multiple_papers(store: ReadStateStore) -> None:
    ids = [f"paper:{i:03d}" for i in range(10)]
    for pid in ids[:5]:
        store.mark_read(pid)
    for pid in ids[:5]:
        assert store.is_read(pid) is True
    for pid in ids[5:]:
        assert store.is_read(pid) is False
