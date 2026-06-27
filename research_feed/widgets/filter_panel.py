"""Filter panel for selecting active paper source."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option


class FilterPanel(ModalScreen[str]):
    """Modal for selecting the source filter."""

    BINDINGS = [
        Binding("escape", "dismiss_default", "Cancel", show=True),
    ]

    def __init__(self, sources: list[str], current: str) -> None:
        super().__init__()
        self._sources = sources
        self._current = current

    def compose(self) -> ComposeResult:
        options = ["All"] + self._sources
        yield Label("Filter by source", id="filter-title")
        yield OptionList(
            *[Option(s, id=s) for s in options],
            id="filter-list",
        )

    def on_mount(self) -> None:
        ol = self.query_one(OptionList)
        options = ["All"] + self._sources
        try:
            idx = options.index(self._current)
            ol.highlighted = idx
        except ValueError:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    def action_dismiss_default(self) -> None:
        self.dismiss(self._current)
