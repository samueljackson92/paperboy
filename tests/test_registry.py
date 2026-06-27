"""Tests for SourceRegistry aggregation and error isolation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from paperboy.models import Paper, SourceKind
from paperboy.sources.base import PaperSource
from paperboy.sources.registry import SourceRegistry


def _paper(title: str, days_ago: int) -> Paper:
    return Paper(
        id=f"test:{title}",
        title=title,
        authors=["Author"],
        abstract="Abstract",
        source="Test",
        kind=SourceKind.ARXIV,
        published=datetime(2024, 1, 20, tzinfo=timezone.utc) - timedelta(days=days_ago),
    )


class MockSource(PaperSource):
    name = "Mock"
    kind = SourceKind.ARXIV

    def __init__(
        self,
        papers: list[Paper] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._papers = papers or []
        self._error = error

    async def fetch_latest(self, limit: int = 50) -> list[Paper]:
        if self._error:
            raise self._error
        return self._papers


@pytest.mark.asyncio
async def test_fetch_all_merges_and_sorts() -> None:
    src_a = MockSource([_paper("Old Paper", 2), _paper("Newest", 0)])
    src_b = MockSource([_paper("Middle", 1)])
    papers = await SourceRegistry([src_a, src_b]).fetch_all()
    assert len(papers) == 3
    assert papers[0].title == "Newest"
    assert papers[1].title == "Middle"
    assert papers[2].title == "Old Paper"


@pytest.mark.asyncio
async def test_fetch_all_isolates_source_error() -> None:
    good = _paper("Good Paper", 0)
    papers = await SourceRegistry([
        MockSource([good]),
        MockSource(error=RuntimeError("network error")),
    ]).fetch_all()
    assert len(papers) == 1
    assert papers[0].title == "Good Paper"


@pytest.mark.asyncio
async def test_fetch_all_all_fail_returns_empty() -> None:
    papers = await SourceRegistry([
        MockSource(error=RuntimeError("down")),
        MockSource(error=ConnectionError("timeout")),
    ]).fetch_all()
    assert papers == []


@pytest.mark.asyncio
async def test_fetch_all_no_sources_returns_empty() -> None:
    assert await SourceRegistry([]).fetch_all() == []
