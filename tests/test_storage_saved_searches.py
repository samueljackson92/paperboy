"""Tests for saved search persistence."""
from pathlib import Path

import pytest

from paperboy.models import FilterState
from paperboy.storage import ReadStateStore


@pytest.fixture
def store(tmp_path: Path) -> ReadStateStore:
    return ReadStateStore(db_path=tmp_path / "test.db")


def test_save_and_retrieve(store: ReadStateStore) -> None:
    state = FilterState(source="arXiv", keywords="fusion", bookmarked_only=False, sort_by="date", sort_desc=True)
    store.save_search("my search", state)
    results = store.get_saved_searches()
    assert len(results) == 1
    name, loaded = results[0]
    assert name == "my search"
    assert loaded.source == "arXiv"
    assert loaded.keywords == "fusion"
    assert loaded.sort_by == "date"
    assert loaded.sort_desc is True


def test_overwrite_existing(store: ReadStateStore) -> None:
    state1 = FilterState(source="arXiv")
    state2 = FilterState(source="NeurIPS")
    store.save_search("test", state1)
    store.save_search("test", state2)
    results = store.get_saved_searches()
    assert len(results) == 1
    assert results[0][1].source == "NeurIPS"


def test_delete_search(store: ReadStateStore) -> None:
    store.save_search("to delete", FilterState())
    store.delete_search("to delete")
    assert store.get_saved_searches() == []


def test_multiple_searches_sorted_by_name(store: ReadStateStore) -> None:
    store.save_search("zebra", FilterState(source="B"))
    store.save_search("alpha", FilterState(source="A"))
    names = [name for name, _ in store.get_saved_searches()]
    assert names == ["alpha", "zebra"]


def test_bookmarked_only_roundtrip(store: ReadStateStore) -> None:
    store.save_search("bm", FilterState(bookmarked_only=True))
    _, loaded = store.get_saved_searches()[0]
    assert loaded.bookmarked_only is True
