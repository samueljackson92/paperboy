"""App-level TUI tests using Textual Pilot."""
from __future__ import annotations

import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from paperboy.app import ResearchFeedApp
from paperboy.config import Config
from paperboy.models import Paper, SourceKind
from paperboy.storage import ReadStateStore
from paperboy.widgets.paper_list import PaperList


def _paper(
    idx: int,
    source: str = "arXiv",
    kind: SourceKind = SourceKind.ARXIV,
    is_read: bool = False,
) -> Paper:
    return Paper(
        id=f"test:{idx}",
        title=f"Paper {idx}",
        authors=["Author A"],
        abstract=f"Abstract for paper {idx}.",
        source=source,
        kind=kind,
        published=datetime(2024, 1, 20 - idx, tzinfo=timezone.utc),
        pdf_url=f"https://arxiv.org/pdf/{idx}",
        is_read=is_read,
    )


class _FakeRegistry:
    def __init__(self, papers: list[Paper]) -> None:
        self._papers = papers

    @property
    def sources(self) -> list[object]:
        return []

    async def fetch_all(self, limit: int = 50) -> list[Paper]:
        return self._papers


def _make_app(papers: list[Paper], tmp_path: Path) -> ResearchFeedApp:
    app = ResearchFeedApp(config=Config())
    app._sources = _FakeRegistry(papers)  # type: ignore[assignment]
    app._store = ReadStateStore(db_path=tmp_path / "test.db")
    return app


@pytest.mark.asyncio
async def test_papers_load_on_mount(tmp_path: Path) -> None:
    papers = [_paper(1), _paper(2), _paper(3)]
    app = _make_app(papers, tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        pl = app.query_one(PaperList)
        assert len(pl._all_papers) == 3


@pytest.mark.asyncio
async def test_filter_by_source(tmp_path: Path) -> None:
    papers = [
        _paper(1, source="arXiv", kind=SourceKind.ARXIV),
        _paper(2, source="NeurIPS 2025", kind=SourceKind.OPENREVIEW),
        _paper(3, source="arXiv", kind=SourceKind.ARXIV),
    ]
    app = _make_app(papers, tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        pl = app.query_one(PaperList)
        pl.active_filter = "arXiv"
        await pilot.pause(0.1)
        assert all(p.source == "arXiv" for p in pl._visible_papers)
        assert len(pl._visible_papers) == 2


@pytest.mark.asyncio
async def test_open_paper_marks_read(tmp_path: Path) -> None:
    papers = [_paper(1, is_read=False)]
    app = _make_app(papers, tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        await pilot.press("enter")
        await pilot.pause(0.3)
        pl = app.query_one(PaperList)
        assert pl._all_papers[0].is_read is True


@pytest.mark.asyncio
async def test_open_pdf_calls_webbrowser(tmp_path: Path) -> None:
    papers = [_paper(1)]
    app = _make_app(papers, tmp_path)
    with patch.object(webbrowser, "open") as mock_open:
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            await pilot.press("o")
            await pilot.pause(0.1)
        mock_open.assert_called_once_with("https://arxiv.org/pdf/1")


@pytest.mark.asyncio
async def test_unread_count_updates(tmp_path: Path) -> None:
    papers = [_paper(1, is_read=False), _paper(2, is_read=False)]
    app = _make_app(papers, tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
        pl = app.query_one(PaperList)
        assert pl.unread_count == 2
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert pl.unread_count == 1
