"""Tests for the Paper domain model."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from paperboy.models import Paper, SourceKind


def _make_paper(**kwargs: object) -> Paper:
    defaults: dict[str, object] = dict(
        id="arxiv:test123",
        title="Test Paper",
        authors=["Alice", "Bob"],
        abstract="An abstract.",
        source="arXiv",
        kind=SourceKind.ARXIV,
        published=datetime(2024, 1, 15, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return Paper(**defaults)  # type: ignore[arg-type]


def test_paper_construction() -> None:
    p = _make_paper()
    assert p.id == "arxiv:test123"
    assert p.title == "Test Paper"
    assert p.authors == ["Alice", "Bob"]
    assert p.is_read is False


def test_paper_frozen() -> None:
    p = _make_paper()
    with pytest.raises((ValidationError, AttributeError, TypeError)):
        p.title = "Changed"  # type: ignore[misc]


def test_paper_with_read_state() -> None:
    p = _make_paper(is_read=False)
    p_read = p.with_read_state(True)
    assert p_read.is_read is True
    assert p_read.id == p.id
    assert p.is_read is False  # original unchanged


def test_source_kind_values() -> None:
    assert SourceKind.ARXIV.value == "arxiv"
    assert SourceKind.OPENREVIEW.value == "openreview"
    assert SourceKind.JOURNAL.value == "journal"


def test_paper_optional_fields() -> None:
    p = _make_paper(pdf_url=None, html_url=None, venue=None)
    assert p.pdf_url is None
    assert p.html_url is None
    assert p.venue is None
    assert p.categories == []


def test_paper_with_read_state_preserves_all_fields() -> None:
    p = _make_paper(
        venue="NeurIPS",
        pdf_url="https://example.com/paper.pdf",
        categories=["cs.LG"],
    )
    p2 = p.with_read_state(True)
    assert p2.venue == p.venue
    assert p2.pdf_url == p.pdf_url
    assert p2.categories == p.categories
