"""Filter panel modal for source, keyword, and bookmark filtering."""
from __future__ import annotations

from dataclasses import dataclass, field

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList
from textual.widgets.option_list import Option


@dataclass
class FilterState:
    source: str = "All"
    keywords: str = ""
    bookmarked_only: bool = False


class FilterPanel(ModalScreen[FilterState]):
    """Modal for filtering papers by source, keywords, and bookmark status."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "apply", "Apply", show=False),
    ]

    def __init__(self, sources: list[str], current: FilterState) -> None:
        super().__init__()
        self._sources = sources
        self._current = current

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
            with Horizontal(id="filter-buttons"):
                yield Button("Cancel", id="filter-cancel", variant="default")
                yield Button("Apply", id="filter-apply", variant="primary")

    def on_mount(self) -> None:
        ol = self.query_one("#filter-source-list", OptionList)
        options = ["All"] + self._sources
        try:
            ol.highlighted = options.index(self._current.source)
        except ValueError:
            ol.highlighted = 0
        self.query_one("#filter-keywords", Input).focus()

    def action_apply(self) -> None:
        self.dismiss(self._build_state())

    def action_cancel(self) -> None:
        self.dismiss(self._current)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "filter-apply":
            self.dismiss(self._build_state())
        elif event.button.id == "filter-cancel":
            self.dismiss(self._current)

    def _build_state(self) -> FilterState:
        ol = self.query_one("#filter-source-list", OptionList)
        source = str(ol.get_option_at_index(ol.highlighted or 0).id) if ol.highlighted is not None else "All"
        keywords = self.query_one("#filter-keywords", Input).value.strip()
        bookmarked = self.query_one("#filter-bookmarked", Checkbox).value
        return FilterState(source=source, keywords=keywords, bookmarked_only=bookmarked)
