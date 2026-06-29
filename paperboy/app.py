"""Main Textual application for paperboy."""
from __future__ import annotations

import dataclasses
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    LoadingIndicator,
    Static,
    TabbedContent,
    TabPane,
)

from paperboy.config import Config, load_config
from paperboy.export import paper_to_bibtex
from paperboy.models import FilterState, Paper
from paperboy.sources.arxiv_source import ArxivSource
from paperboy.sources.journal_source import JournalSource
from paperboy.sources.openreview_source import OpenReviewSource
from paperboy.sources.registry import SourceRegistry
from paperboy.sources.semantic_scholar import SemanticScholarEnricher
from paperboy.storage import ReadStateStore
from paperboy.widgets.detail_view import DetailView
from paperboy.widgets.export_panel import ExportPanel
from paperboy.widgets.filter_panel import FilterPanel
from paperboy.widgets.paper_list import PaperList
from paperboy.widgets.source_panel import SourcePanel

logger = logging.getLogger(__name__)

_FEED_TAB = "tab-feed"
_BOOKMARKS_TAB = "tab-bookmarks"
_FEED_LIST = "feed-list"
_BOOKMARKS_LIST = "bookmark-list"


class ResearchFeedApp(App[None]):
    """Paperboy — terminal reader for academic papers."""

    TITLE = "paperboy"
    CSS_PATH = Path(__file__).parent / "paperboy.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("f", "filter", "Filter", show=True),
        Binding("e", "export", "Export", show=True),
        Binding("o", "open_pdf", "Open", show=True),
        Binding("y", "copy_bibtex", "Copy BibTeX", show=False),
        Binding("j", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
    ]

    last_refresh: reactive[str] = reactive("Never")
    loading: reactive[bool] = reactive(False)

    def __init__(self, config: Config | None = None) -> None:
        super().__init__()
        self._config = config or load_config()
        self._store = ReadStateStore()
        self._sources = self._build_registry()
        self._all_papers: list[Paper] = []
        self._enricher: SemanticScholarEnricher | None = None

    def _build_registry(self) -> SourceRegistry:
        cfg = self._config
        sources = [
            ArxivSource(
                categories=cfg.arxiv.categories,
                keywords=cfg.arxiv.keywords,
                query=cfg.arxiv.query,
            ),
            *[
                OpenReviewSource(venue_id=v.id, keywords=v.keywords)
                for v in cfg.openreview.venues
            ],
            *[
                JournalSource(name=j.name, feed_url=j.feed_url, keywords=j.keywords)
                for j in cfg.journals
            ],
        ]
        return SourceRegistry(sources)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar")
        with TabbedContent(id="main-tabs"):
            with TabPane("Feed", id=_FEED_TAB):
                with Horizontal(id="feed-area"):
                    yield SourcePanel(id="source-panel")
                    yield PaperList(id=_FEED_LIST)
            with TabPane("Bookmarks ★", id=_BOOKMARKS_TAB):
                yield PaperList(id=_BOOKMARKS_LIST)
        yield LoadingIndicator(id="loading")
        yield DetailView(id="detail-view")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#loading", LoadingIndicator).display = False
        self.action_refresh()
        interval = self._config.app.refresh_interval_minutes * 60
        if interval > 0:
            self.set_interval(interval, self.action_refresh)

    def watch_loading(self, value: bool) -> None:
        self.query_one("#loading", LoadingIndicator).display = value
        self.query_one("#main-tabs", TabbedContent).display = not value

    def _active_list(self) -> PaperList:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        list_id = _BOOKMARKS_LIST if active == _BOOKMARKS_TAB else _FEED_LIST
        return self.query_one(f"#{list_id}", PaperList)

    def _apply_paper_update(self, updated: Paper) -> None:
        self._all_papers = [updated if p.id == updated.id else p for p in self._all_papers]
        self.query_one(f"#{_FEED_LIST}", PaperList).update_paper(updated)
        bookmarked = [p for p in self._all_papers if p.is_bookmarked]
        self.query_one(f"#{_BOOKMARKS_LIST}", PaperList).set_papers(bookmarked)
        unread_by_source: dict[str, int] = Counter(
            p.source for p in self._all_papers if not p.is_read
        )
        feed_list = self.query_one(f"#{_FEED_LIST}", PaperList)
        self.query_one("#source-panel", SourcePanel).set_sources(
            feed_list.source_names, unread_by_source
        )

    def _update_status(self) -> None:
        pl = self.query_one(f"#{_FEED_LIST}", PaperList)
        f = pl.current_filter
        parts = [f"Unread: [bold]{pl.unread_count}[/bold]"]
        if pl.bookmark_count:
            parts.append(f"Bookmarked: [bold]{pl.bookmark_count}[/bold]")
        parts.append(f"Last refresh: {self.last_refresh}")
        active = []
        if f.source != "All":
            active.append(f.source)
        if f.keywords:
            active.append(f'"{f.keywords}"')
        if f.bookmarked_only:
            active.append("bookmarked")
        if active:
            parts.append(f"Filter: {', '.join(active)}")
        self.query_one("#status-bar", Static).update("  |  ".join(parts))

    @work(exclusive=True)
    async def action_refresh(self) -> None:
        self.loading = True
        try:
            papers = await self._sources.fetch_all(limit=self._config.app.max_papers)
            read_ids = self._store.get_all_read_ids()
            bookmarked_ids = self._store.get_all_bookmarked_ids()
            self._all_papers = [
                p.model_copy(update={
                    "is_read": p.id in read_ids,
                    "is_bookmarked": p.id in bookmarked_ids,
                })
                for p in papers
            ]

            if self._config.semantic_scholar.api_key:
                if self._enricher is None:
                    self._enricher = SemanticScholarEnricher(self._config.semantic_scholar.api_key)
                self._all_papers = await self._enricher.enrich_citations(self._all_papers)

            feed_list = self.query_one(f"#{_FEED_LIST}", PaperList)
            feed_list.set_papers(self._all_papers)
            bookmarked = [p for p in self._all_papers if p.is_bookmarked]
            self.query_one(f"#{_BOOKMARKS_LIST}", PaperList).set_papers(bookmarked)
            unread_by_source: dict[str, int] = Counter(
                p.source for p in self._all_papers if not p.is_read
            )
            self.query_one("#source-panel", SourcePanel).set_sources(
                feed_list.source_names, unread_by_source
            )
            self.last_refresh = datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC")
            feed_list.query_one(DataTable).focus()
        except Exception as exc:
            logger.error("Refresh failed: %s", exc)
            self.notify(f"Refresh error: {exc}", severity="error")
        finally:
            self.loading = False
        self._update_status()

    def action_filter(self) -> None:
        pl = self._active_list()

        def handle_filter(result: FilterState | None) -> None:
            if isinstance(result, FilterState):
                pl.apply_filters(result)
                self.query_one("#source-panel", SourcePanel).set_active_source(result.source)
                self._update_status()

        self.push_screen(
            FilterPanel(pl.source_names, pl.current_filter),
            handle_filter,
        )

    def on_source_panel_source_selected(self, event: SourcePanel.SourceSelected) -> None:
        for list_id in (_FEED_LIST, _BOOKMARKS_LIST):
            pl = self.query_one(f"#{list_id}", PaperList)
            pl.apply_filters(dataclasses.replace(pl.current_filter, source=event.source))
        self._update_status()

    def action_export(self) -> None:
        self.push_screen(ExportPanel(self._active_list()._visible_papers))

    def action_open_pdf(self) -> None:
        self.query_one("#detail-view", DetailView).open_pdf()

    def action_copy_bibtex(self) -> None:
        detail = self.query_one("#detail-view", DetailView)
        paper = detail._current_paper
        if paper is None:
            return
        bib = paper_to_bibtex(paper)
        try:
            self.copy_to_clipboard(bib)
            self.notify("BibTeX copied", timeout=1.5)
        except Exception:
            self.notify("Clipboard unavailable — BibTeX logged", severity="warning", timeout=2)
            logger.info("BibTeX:\n%s", bib)

    def action_move_down(self) -> None:
        self._active_list().query_one(DataTable).action_scroll_down()

    def action_move_up(self) -> None:
        self._active_list().query_one(DataTable).action_scroll_up()

    def on_paper_list_paper_highlighted(self, event: PaperList.PaperHighlighted) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        expected = _BOOKMARKS_LIST if tabs.active == _BOOKMARKS_TAB else _FEED_LIST
        if event.sender_id == expected or event.sender_id == "":
            self.query_one("#detail-view", DetailView).show_paper(event.paper)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        active_list = self._active_list()
        table = active_list.query_one(DataTable)
        if table.cursor_row < len(active_list._visible_papers):
            paper = active_list._visible_papers[table.cursor_row]
            self.query_one("#detail-view", DetailView).show_paper(paper)
        self._update_status()

    def on_paper_list_paper_selected(self, event: PaperList.PaperSelected) -> None:
        paper = event.paper
        updated = paper.with_read_state(True)
        self._store.mark_read(paper.id)
        self._apply_paper_update(updated)
        self._update_status()

    def on_paper_list_paper_toggled(self, event: PaperList.PaperToggled) -> None:
        paper = event.paper
        new_read = not paper.is_read
        if new_read:
            self._store.mark_read(paper.id)
        else:
            self._store.mark_unread(paper.id)
        self._apply_paper_update(paper.with_read_state(new_read))
        self._update_status()

    def on_paper_list_paper_bookmarked(self, event: PaperList.PaperBookmarked) -> None:
        paper = event.paper
        new_state = self._store.toggle_bookmark(paper.id)
        updated = paper.with_bookmark_state(new_state)
        self._apply_paper_update(updated)
        label = "Bookmarked ★" if new_state else "Bookmark removed"
        self.notify(label, timeout=1.5)
        self._update_status()


def main() -> None:
    """Entry point for the paperboy console script."""
    logging.basicConfig(level=logging.WARNING)
    ResearchFeedApp().run()


if __name__ == "__main__":
    main()
