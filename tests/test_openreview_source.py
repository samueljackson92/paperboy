"""Tests for OpenReviewSource with mocked client."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from research_feed.models import SourceKind
from research_feed.sources.openreview_source import OpenReviewSource


def _note(
    note_id: str = "abc123",
    title: str = "Test Paper",
    abstract: str = "A great abstract.",
    authors: list[str] | None = None,
    cdate: int = 1_700_000_000_000,
    with_pdf: bool = True,
) -> MagicMock:
    note = MagicMock()
    note.id = note_id
    note.tcdate = cdate
    note.cdate = cdate
    content: dict[str, object] = {
        "title": {"value": title},
        "abstract": {"value": abstract},
        "authors": {"value": authors or ["Alice", "Bob"]},
        "keywords": {"value": ["deep learning", "transformers"]},
    }
    if with_pdf:
        content["pdf"] = {"value": "/pdf/abc123"}
    note.content = content
    return note


def _client(notes: list[MagicMock]) -> MagicMock:
    c = MagicMock()
    c.get_all_notes.return_value = notes
    return c


@pytest.mark.asyncio
async def test_fetch_latest_basic() -> None:
    src = OpenReviewSource(
        venue_id="NeurIPS.cc/2025/Conference",
        client=_client([_note("n1", "Paper One"), _note("n2", "Paper Two")]),
    )
    papers = await src.fetch_latest(limit=10)

    assert len(papers) == 2
    assert papers[0].title == "Paper One"
    assert papers[0].kind == SourceKind.OPENREVIEW
    assert papers[0].authors == ["Alice", "Bob"]
    assert "openreview.net" in (papers[0].pdf_url or "")


@pytest.mark.asyncio
async def test_fetch_latest_missing_pdf() -> None:
    src = OpenReviewSource(
        venue_id="ICML.cc/2025/Conference",
        client=_client([_note(with_pdf=False)]),
    )
    papers = await src.fetch_latest(limit=10)
    assert papers[0].pdf_url is None


@pytest.mark.asyncio
async def test_fetch_latest_empty() -> None:
    src = OpenReviewSource(venue_id="ICML.cc/2025/Conference", client=_client([]))
    papers = await src.fetch_latest(limit=10)
    assert papers == []


@pytest.mark.asyncio
async def test_fetch_latest_client_error_propagates() -> None:
    mock_client = MagicMock()
    mock_client.get_all_notes.side_effect = RuntimeError("API down")
    src = OpenReviewSource(venue_id="NeurIPS.cc/2025/Conference", client=mock_client)

    with pytest.raises(RuntimeError, match="API down"):
        await src.fetch_latest(limit=10)


def test_friendly_name() -> None:
    src = OpenReviewSource(venue_id="NeurIPS.cc/2025/Conference", client=MagicMock())
    assert "NeurIPS" in src.name
    assert "2025" in src.name
