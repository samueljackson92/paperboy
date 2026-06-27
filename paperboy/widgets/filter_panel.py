"""Filter panel modal for source, keyword, bookmark, and sort filtering."""
from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Select
from textual.widgets.option_list import Option

from paperboy.models import FilterState


@dataclass
class SavedFilterResult:
    """Returned by FilterPanel when user chooses to save the search."""

    state: FilterState
    name: str


_SORT_OPTIONS: list[tuple[str, str]] = [
    ("Date ↓ (newest)", "date_desc"),
    ("Date ↑ (oldest)", "date_asc"),
    ("Source A→Z", "source_asc"),
    ("Title A→Z", "title_asc"),
]


def _sort_value(state: FilterState) -> str:
    if state.sort_by == "source":
        return "source_asc"
    if state.sort_by == "title":
        return "title_asc"
    return "date_desc" if state.sort_desc else "date_asc"


def _decode_sort(value: str) -> tuple[str, bool]:
    """Return (sort_by, sort_desc) from select value."""
    if value == "date_asc":
        return "date", False
    if value == "source_asc":
        return "source", True
    if value == "title_asc":
        return "title", True
    return "date", True


class FilterPanel(ModalScreen[FilterState | SavedFilterResult]):
    """Modal for filtering papers by source, keywords, bookmark status, and sort order."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, sources: list[str], current: FilterState) -> None:
        super().__init__()
        self._sources = sources
        self._current = current
        self._saving = False

    def compose(self) -> ComposeResult:
        options = ["All"] + self._sources
        with Vertical(id="filter-container"):
            yield Label("Filter papers", id="filter-title")
            yield Label("Keywords", classes="filter-label")
            yield Input(
                value=self._current.keywords,
                placeholder="Search title and abstract…",
                id="filter-keywords",
            )
            yield Label("Source", classes="filter-label")
            yield OptionList(
                *[Option(s, id=s) for s in options],
                id="filter-source-list",
            )
            yield Checkbox(
                "Bookmarked only",
                value=self._current.bookmarked_only,
                id="filter-bookmarked",
            )
            yield Label("Sort", classes="filter-label")
            yield Select(
                [(label, val) for label, val in _SORT_OPTIONS],
                value=_sort_value(self._current),
                id="filter-sort",
            )
            with Horizontal(id="filter-buttons"):
                yield Button("Cancel", id="filter-cancel", variant="default")
                yield Button("Save…", id="filter-save", variant="default")
                yield Button("Apply", id="filter-apply", variant="primary")
            yield Input(
                placeholder="Search name…",
                id="save-name",
            )

    def on_mount(self) -> None:
        ol = self.query_one("#filter-source-list", OptionList)
        options = ["All"] + self._sources
        try:
            ol.highlighted = options.index(self._current.source)
        except ValueError:
            ol.highlighted = 0
        self.query_one("#save-name", Input).display = False
        self.query_one("#filter-keywords", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(self._current)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "filter-apply":
            self.dismiss(self._build_state())
        elif event.button.id == "filter-cancel":
            self.dismiss(self._current)
        elif event.button.id == "filter-save":
            save_input = self.query_one("#save-name", Input)
            save_input.display = True
            save_input.focus()
            self._saving = True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "save-name" and self._saving:
            name = event.value.strip()
            if name:
                self.dismiss(SavedFilterResult(state=self._build_state(), name=name))
            else:
                event.input.display = False
                self._saving = False

    def _build_state(self) -> FilterState:
        ol = self.query_one("#filter-source-list", OptionList)
        source = str(ol.get_option_at_index(ol.highlighted or 0).id) if ol.highlighted is not None else "All"
        keywords = self.query_one("#filter-keywords", Input).value.strip()
        bookmarked = self.query_one("#filter-bookmarked", Checkbox).value
        sort_sel = self.query_one("#filter-sort", Select)
        sort_by, sort_desc = _decode_sort(str(sort_sel.value) if sort_sel.value else "date_desc")
        return FilterState(
            source=source,
            keywords=keywords,
            bookmarked_only=bookmarked,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )
