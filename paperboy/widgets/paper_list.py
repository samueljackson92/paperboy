"""Paper list widget showing all fetched papers."""
from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Input

from paperboy.models import FilterState, Paper

UNREAD = "●"
BOOKMARK = "★"

_SORT_KEY = {
    "date": lambda p: p.published,
    "title": lambda p: p.title.lower(),
    "source": lambda p: p.source.lower(),
}


class PaperList(Widget):
    """Displays a filterable, scrollable list of papers."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "select_paper", "Open", show=True),
        Binding("space", "toggle_read", "Toggle read", show=True),
        Binding("b", "toggle_bookmark", "Bookmark", show=True),
        Binding("/", "start_search", "Search", show=False),
        Binding("n", "next_match", "Next match", show=False),
        Binding("N", "prev_match", "Prev match", show=False),
        Binding("escape", "close_search", "Close search", show=False),
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
        self._search_matches: list[int] = []
        self._search_idx: int = 0

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(cursor_type="row", zebra_stripes=True)
        yield table
        yield Input(id="vim-search", placeholder="/search…")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("", "Title", "Source", "Authors", "Date", "Cited")
        self._search_bar.display = False
        self._refresh_table()

    @property
    def _search_bar(self) -> Input:
        return self.query_one("#vim-search", Input)

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
        self._filter = FilterState(
            source=value,
            keywords=self._filter.keywords,
            bookmarked_only=self._filter.bookmarked_only,
            sort_by=self._filter.sort_by,
            sort_desc=self._filter.sort_desc,
        )
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

        sort_fn = _SORT_KEY.get(self._filter.sort_by, _SORT_KEY["date"])
        self._visible_papers.sort(key=sort_fn, reverse=self._filter.sort_desc)

        for paper in self._visible_papers:
            indicator = (BOOKMARK if paper.is_bookmarked else " ") + (UNREAD if not paper.is_read else " ")
            title = paper.title[:70] + "…" if len(paper.title) > 70 else paper.title
            authors_str = ", ".join(paper.authors[:2])
            if len(paper.authors) > 2:
                authors_str += f" +{len(paper.authors) - 2}"
            date_str = paper.published.strftime("%Y-%m-%d")
            cited = str(paper.citation_count) if paper.citation_count is not None else "–"
            table.add_row(
                indicator,
                title,
                paper.source[:20],
                authors_str[:30],
                date_str,
                cited,
                key=paper.id,
            )

        if self._visible_papers:
            self.post_message(self.PaperHighlighted(self._visible_papers[0], sender_id=self.id or ""))

    # ── vim search ──────────────────────────────────────────────────────────

    def action_start_search(self) -> None:
        bar = self._search_bar
        bar.display = True
        bar.value = ""
        bar.focus()
        self._search_matches = []
        self._search_idx = 0

    def action_close_search(self) -> None:
        if self._search_bar.display:
            self._search_bar.display = False
            self.query_one(DataTable).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "vim-search":
            return
        query = event.value.lower()
        if not query:
            self._search_matches = []
            return
        self._search_matches = [
            i for i, p in enumerate(self._visible_papers) if query in p.title.lower()
        ]
        self._search_idx = 0
        self._jump_to_match()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "vim-search":
            self._search_bar.display = False
            self.query_one(DataTable).focus()

    def action_next_match(self) -> None:
        if not self._search_matches:
            return
        self._search_idx = (self._search_idx + 1) % len(self._search_matches)
        self._jump_to_match()

    def action_prev_match(self) -> None:
        if not self._search_matches:
            return
        self._search_idx = (self._search_idx - 1) % len(self._search_matches)
        self._jump_to_match()

    def _jump_to_match(self) -> None:
        if not self._search_matches:
            return
        row = self._search_matches[self._search_idx]
        self.query_one(DataTable).move_cursor(row=row)

    # ── actions ─────────────────────────────────────────────────────────────

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
