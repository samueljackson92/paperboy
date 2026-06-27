"""Paper list widget showing all fetched papers."""
from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable

from paperboy.models import Paper

UNREAD_INDICATOR = "●"
READ_INDICATOR = " "


class PaperList(Widget):
    """Displays a filterable, scrollable list of papers."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "select_paper", "Open", show=True),
        Binding("space", "toggle_read", "Toggle read", show=True),
    ]

    active_filter: reactive[str] = reactive("All")

    class PaperSelected(Message):
        def __init__(self, paper: Paper) -> None:
            super().__init__()
            self.paper = paper

    class PaperToggled(Message):
        def __init__(self, paper: Paper) -> None:
            super().__init__()
            self.paper = paper

    class PaperHighlighted(Message):
        def __init__(self, paper: Paper) -> None:
            super().__init__()
            self.paper = paper

    def __init__(self, papers: list[Paper] | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._all_papers: list[Paper] = papers or []
        self._visible_papers: list[Paper] = []

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(cursor_type="row", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("", "Title", "Source", "Authors", "Date")
        self._refresh_table()

    def set_papers(self, papers: list[Paper]) -> None:
        """Replace the full paper list and re-render."""
        self._all_papers = papers
        self._refresh_table()

    def watch_active_filter(self, value: str) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        filt = self.active_filter
        self._visible_papers = [
            p for p in self._all_papers
            if filt == "All" or p.source == filt
        ]
        for paper in self._visible_papers:
            indicator = READ_INDICATOR if paper.is_read else UNREAD_INDICATOR
            title = paper.title[:72] + "…" if len(paper.title) > 72 else paper.title
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
        # Ensure the detail pane reflects the first visible paper after every rebuild.
        if self._visible_papers:
            self.post_message(self.PaperHighlighted(self._visible_papers[0]))

    def action_select_paper(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperSelected(self._visible_papers[table.cursor_row]))

    def action_toggle_read(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperToggled(self._visible_papers[table.cursor_row]))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperSelected(self._visible_papers[event.cursor_row]))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.cursor_row < len(self._visible_papers):
            self.post_message(self.PaperHighlighted(self._visible_papers[event.cursor_row]))

    def update_paper(self, updated: Paper) -> None:
        """Replace one paper in-place and re-render."""
        self._all_papers = [
            updated if p.id == updated.id else p for p in self._all_papers
        ]
        self._refresh_table()

    @property
    def unread_count(self) -> int:
        return sum(1 for p in self._all_papers if not p.is_read)

    @property
    def source_names(self) -> list[str]:
        seen: list[str] = []
        for p in self._all_papers:
            if p.source not in seen:
                seen.append(p.source)
        return seen
