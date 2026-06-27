"""Saved searches modal."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from paperboy.models import FilterState
from paperboy.storage import ReadStateStore


class SavedSearchPanel(ModalScreen[FilterState | None]):
    """Modal listing saved searches; lets user apply or delete them."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(self, store: ReadStateStore, current: FilterState) -> None:
        super().__init__()
        self._store = store
        self._current = current
        self._searches: list[tuple[str, FilterState]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="saved-container"):
            yield Label("Saved searches", id="saved-title")
            yield DataTable(id="saved-table", cursor_type="row")
            yield Static("No saved searches yet. Use F→Save… in the filter panel.", id="saved-empty")
            with Horizontal(id="saved-buttons"):
                yield Button("Close", id="saved-close", variant="default")
                yield Button("Delete", id="saved-delete", variant="error")
                yield Button("Apply", id="saved-apply", variant="primary")

    def on_mount(self) -> None:
        table = self.query_one("#saved-table", DataTable)
        table.add_columns("Name", "Source", "Keywords", "Sort")
        self._reload()

    def _reload(self) -> None:
        self._searches = self._store.get_saved_searches()
        table = self.query_one("#saved-table", DataTable)
        table.clear()
        empty = self.query_one("#saved-empty", Static)
        if self._searches:
            empty.display = False
            table.display = True
            for name, state in self._searches:
                sort_label = f"{state.sort_by} {'↓' if state.sort_desc else '↑'}"
                table.add_row(name, state.source, state.keywords or "—", sort_label)
        else:
            empty.display = True
            table.display = False

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "saved-close":
            self.dismiss(None)
        elif event.button.id == "saved-apply":
            self._apply_selected()
        elif event.button.id == "saved-delete":
            self._delete_selected()

    def _apply_selected(self) -> None:
        table = self.query_one("#saved-table", DataTable)
        if table.cursor_row < len(self._searches):
            _, state = self._searches[table.cursor_row]
            self.dismiss(state)

    def _delete_selected(self) -> None:
        table = self.query_one("#saved-table", DataTable)
        if table.cursor_row < len(self._searches):
            name, _ = self._searches[table.cursor_row]
            self._store.delete_search(name)
            self._reload()
