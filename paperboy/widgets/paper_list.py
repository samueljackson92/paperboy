"""Paper list widget showing all fetched papers."""
from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable

from paperboy.models import Paper
from paperboy.widgets.filter_panel import FilterState

UNREAD = "●"
BOOKMARK = "★"


class PaperList(Widget):
    """Displays a filterable, scrollable list of papers."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "select_paper", "Open", show=True),
        Binding("space", "toggle_read", "Toggle read", show=True),
        Binding("b", "toggle_bookmark", "Bookmark", show=True),
    ]

    class PaperSelected(Message):
        def __init__(self, paper: Paper) -> None:
            super().__init__()
            self.paper = paper

    class PaperToggled(Message):
        def __init__(self, paper: Paper) -> None:
            super().__init__()
            self.paper = paper

    class PaperHighlighted(Message):
        def __init__(self, paper: Paper, sender_id: str = "") -> None:
            super().__init__()
            self.paper = paper
            self.sender_id = sender_id

    class PaperBookmarked(Message):
        def __init__(self, paper: Paper) -> None:
            super().__init__()
            self.paper = paper

    def __init__(self, papers: list[Paper] | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._all_papers: list[Paper] = papers or []
        self._visible_papers: list[Paper] = []
        self._filter = FilterState()

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(cursor_type="row", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("", "Title", "Source", "Authors", "Date")
        self._refresh_table()

    def set_papers(self, papers: list[Paper]) -> None:
        self._all_papers = papers
        self._refresh_table()

    def apply_filters(self, state: FilterState) -> None:
        self._filter = state
        self._refresh_table()

    @property
    def current_filter(self) -> FilterState:
        return self._filter

    # kept for backwards-compat with tests
    @property
    def active_filter(self) -> str:
        return self._filter.source

    @active_filter.setter
    def active_filter(self, value: str) -> None:
        self._filter = FilterState(source=value, keywords=self._filter.keywords,
                                   bookmarked_only=self._filter.bookmarked_only)
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()

        kw = self._filter.keywords.lower()
        self._visible_papers = [
            p for p in self._all_papers
            if (self._filter.source == "All" or p.source == self._filter.source)
            and (not kw or kw in p.title.lower() or kw in p.abstract.lower())
            and (not self._filter.bookmarked_only or p.is_bookmarked)
        ]

        for paper in self._visible_papers:
            indicator = (BOOKMARK if paper.is_bookmarked else " ") + (UNREAD if not paper.is_read else " ")
            title = paper.title[:70] + "…" if len(paper.title) > 70 else paper.title
            authors_str = ", ".join(paper.authors[:2])
            if len(paper.authors) > 2:
                authors_str += f" +{len(paper.authors) - 2}"
            date_str = paper.published.strftime("%Y-%m-%d")
            table.add_row(
                indicator,
                title,
                paper.source[:20],
                authors_str[:30],
                date_str,
                key=paper.id,
            )

        if self._visible_papers:
            self.post_message(self.PaperHighlighted(self._visible_papers[0], sender_id=self.id or ""))

    def action_select_paper(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperSelected(self._visible_papers[table.cursor_row]))

    def action_toggle_read(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperToggled(self._visible_papers[table.cursor_row]))

    def action_toggle_bookmark(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperBookmarked(self._visible_papers[table.cursor_row]))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperSelected(self._visible_papers[event.cursor_row]))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperHighlighted(self._visible_papers[event.cursor_row], sender_id=self.id or ""))

    def update_paper(self, updated: Paper) -> None:
        self._all_papers = [updated if p.id == updated.id else p for p in self._all_papers]
        self._refresh_table()

    @property
    def unread_count(self) -> int:
        return sum(1 for p in self._all_papers if not p.is_read)

    @property
    def bookmark_count(self) -> int:
        return sum(1 for p in self._all_papers if p.is_bookmarked)

    @property
    def source_names(self) -> list[str]:
        seen: list[str] = []
        for p in self._all_papers:
            if p.source not in seen:
                seen.append(p.source)
        return seen
