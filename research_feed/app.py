"""Main Textual application for paperboy."""
from __future__ import annotations

import logging
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, LoadingIndicator, Static

from research_feed.config import Config, load_config
from research_feed.models import Paper
from research_feed.sources.arxiv_source import ArxivSource
from research_feed.sources.journal_source import JournalSource
from research_feed.sources.openreview_source import OpenReviewSource
from research_feed.sources.registry import SourceRegistry
from research_feed.storage import ReadStateStore
from research_feed.widgets.detail_view import DetailView
from research_feed.widgets.filter_panel import FilterPanel
from research_feed.widgets.paper_list import PaperList

logger = logging.getLogger(__name__)


class ResearchFeedApp(App[None]):
    """Paperboy — terminal reader for academic papers."""

    CSS_PATH = Path(__file__).parent / "research_feed.tcss"

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
        self._registry = self._build_registry()

    def _build_registry(self) -> SourceRegistry:
        cfg = self._config
        sources = [
            ArxivSource(categories=cfg.arxiv.categories, query=cfg.arxiv.query),
            *[OpenReviewSource(venue_id=v) for v in cfg.openreview.venues],
            *[JournalSource(name=j.name, feed_url=j.feed_url) for j in cfg.journals],
        ]
        return SourceRegistry(sources)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar")
        yield PaperList(id="paper-list")
        yield LoadingIndicator(id="loading")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#loading", LoadingIndicator).display = False
        self.action_refresh()

    def watch_loading(self, value: bool) -> None:
        self.query_one("#loading", LoadingIndicator).display = value
        self.query_one("#paper-list", PaperList).display = not value

    def _update_status(self) -> None:
        pl = self.query_one("#paper-list", PaperList)
        unread = pl.unread_count
        self.query_one("#status-bar", Static).update(
            f"Unread: [bold]{unread}[/bold]  |  Last refresh: {self.last_refresh}"
        )

    @work(exclusive=True)
    async def action_refresh(self) -> None:
        """Fetch papers from all sources in a background worker."""
        self.loading = True
        try:
            papers = await self._registry.fetch_all(limit=self._config.app.max_papers)
            read_ids = self._store.get_all_read_ids()
            papers = [p.with_read_state(p.id in read_ids) for p in papers]
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

        def handle_filter(result: str | None) -> None:
            if result is not None:
                pl.active_filter = result
                self._update_status()

        self.push_screen(FilterPanel(pl.source_names, pl.active_filter), handle_filter)

    def action_open_pdf(self) -> None:
        pl = self.query_one("#paper-list", PaperList)
        table = pl.query_one(DataTable)
        if table.cursor_row < len(pl._visible_papers):
            paper = pl._visible_papers[table.cursor_row]
            if paper.pdf_url:
                webbrowser.open(paper.pdf_url)
            else:
                self.notify("No PDF URL available", severity="warning")

    def action_move_down(self) -> None:
        pl = self.query_one("#paper-list", PaperList)
        pl.query_one(DataTable).action_scroll_down()

    def action_move_up(self) -> None:
        pl = self.query_one("#paper-list", PaperList)
        pl.query_one(DataTable).action_scroll_up()

    def on_paper_list_paper_selected(self, event: PaperList.PaperSelected) -> None:
        paper = event.paper
        updated = paper.with_read_state(True)
        self._store.mark_read(paper.id)
        pl = self.query_one("#paper-list", PaperList)
        pl.update_paper(updated)
        self._update_status()

        def after_detail(_: None) -> None:
            self._update_status()

        self.push_screen(DetailView(updated), after_detail)

    def on_paper_list_paper_toggled(self, event: PaperList.PaperToggled) -> None:
        paper = event.paper
        new_read = not paper.is_read
        if new_read:
            self._store.mark_read(paper.id)
        else:
            self._store.mark_unread(paper.id)
        pl = self.query_one("#paper-list", PaperList)
        pl.update_paper(paper.with_read_state(new_read))
        self._update_status()


def main() -> None:
    """Entry point for the paperboy console script."""
    logging.basicConfig(level=logging.WARNING)
    ResearchFeedApp().run()


if __name__ == "__main__":
    main()
