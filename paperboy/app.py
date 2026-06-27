"""Main Textual application for paperboy."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, LoadingIndicator, Static

from paperboy.config import Config, load_config
from paperboy.models import Paper
from paperboy.sources.arxiv_source import ArxivSource
from paperboy.sources.journal_source import JournalSource
from paperboy.sources.openreview_source import OpenReviewSource
from paperboy.sources.registry import SourceRegistry
from paperboy.storage import ReadStateStore
from paperboy.widgets.detail_view import DetailView
from paperboy.widgets.filter_panel import FilterPanel
from paperboy.widgets.paper_list import PaperList

logger = logging.getLogger(__name__)


class ResearchFeedApp(App[None]):
    """Paperboy — terminal reader for academic papers."""

    CSS_PATH = Path(__file__).parent / "paperboy.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("f", "filter", "Filter", show=True),
        Binding("o", "open_pdf", "Open PDF", show=True),
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
        yield PaperList(id="paper-list")
        yield LoadingIndicator(id="loading")
        yield DetailView(id="detail-view")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#loading", LoadingIndicator).display = False
        self.action_refresh()

    def watch_loading(self, value: bool) -> None:
        self.query_one("#loading", LoadingIndicator).display = value
        self.query_one("#paper-list", PaperList).display = not value

    def _update_status(self) -> None:
        pl = self.query_one("#paper-list", PaperList)
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
            papers = [
                p.model_copy(update={
                    "is_read": p.id in read_ids,
                    "is_bookmarked": p.id in bookmarked_ids,
                })
                for p in papers
            ]
            pl = self.query_one("#paper-list", PaperList)
            pl.set_papers(papers)
            self.last_refresh = datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC")
        except Exception as exc:
            logger.error("Refresh failed: %s", exc)
            self.notify(f"Refresh error: {exc}", severity="error")
        finally:
            self.loading = False
        self._update_status()

    def action_filter(self) -> None:
        pl = self.query_one("#paper-list", PaperList)

        def handle_filter(result: object) -> None:
            from paperboy.widgets.filter_panel import FilterState
            if isinstance(result, FilterState):
                pl.apply_filters(result)
                self._update_status()

        self.push_screen(
            FilterPanel(pl.source_names, pl.current_filter),
            handle_filter,
        )

    def action_open_pdf(self) -> None:
        self.query_one("#detail-view", DetailView).open_pdf()

    def action_move_down(self) -> None:
        self.query_one("#paper-list", PaperList).query_one(DataTable).action_scroll_down()

    def action_move_up(self) -> None:
        self.query_one("#paper-list", PaperList).query_one(DataTable).action_scroll_up()

    def on_paper_list_paper_highlighted(self, event: PaperList.PaperHighlighted) -> None:
        self.query_one("#detail-view", DetailView).show_paper(event.paper)

    def on_paper_list_paper_selected(self, event: PaperList.PaperSelected) -> None:
        paper = event.paper
        updated = paper.with_read_state(True)
        self._store.mark_read(paper.id)
        self.query_one("#paper-list", PaperList).update_paper(updated)
        self._update_status()

    def on_paper_list_paper_toggled(self, event: PaperList.PaperToggled) -> None:
        paper = event.paper
        new_read = not paper.is_read
        if new_read:
            self._store.mark_read(paper.id)
        else:
            self._store.mark_unread(paper.id)
        self.query_one("#paper-list", PaperList).update_paper(paper.with_read_state(new_read))
        self._update_status()

    def on_paper_list_paper_bookmarked(self, event: PaperList.PaperBookmarked) -> None:
        paper = event.paper
        new_state = self._store.toggle_bookmark(paper.id)
        updated = paper.with_bookmark_state(new_state)
        self.query_one("#paper-list", PaperList).update_paper(updated)
        label = "Bookmarked ★" if new_state else "Bookmark removed"
        self.notify(label, timeout=1.5)
        self._update_status()


def main() -> None:
    """Entry point for the paperboy console script."""
    logging.basicConfig(level=logging.WARNING)
    ResearchFeedApp().run()


if __name__ == "__main__":
    main()
