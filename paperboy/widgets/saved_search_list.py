"""Saved searches tab widget."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, DataTable, Label, Static

from paperboy.models import FilterState
from paperboy.storage import ReadStateStore


class SavedSearchList(Widget):
    """Lists saved searches; posts SearchApplied when the user selects one."""

    class SearchApplied(Message):
        def __init__(self, state: FilterState) -> None:
            super().__init__()
            self.state = state

    BINDINGS = [
        Binding("enter", "apply", "Apply", show=True),
        Binding("d", "delete", "Delete", show=True),
    ]

    def __init__(self, store: ReadStateStore, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._store = store
        self._searches: list[tuple[str, FilterState]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="searches-inner"):
            yield Label("Saved searches", id="searches-title")
            yield Static(
                "No saved searches yet — use [bold cyan]f[/bold cyan] → Save… to create one.",
                id="searches-empty",
            )
            yield DataTable(id="searches-table", cursor_type="row")
            with Horizontal(id="searches-buttons"):
                yield Button("Apply [enter]", id="searches-apply", variant="primary")
                yield Button("Delete [d]", id="searches-delete", variant="error")

    def on_mount(self) -> None:
        table = self.query_one("#searches-table", DataTable)
        table.add_columns("Name", "Source", "Keywords", "Sort")
        self.reload()

    def reload(self) -> None:
        self._searches = self._store.get_saved_searches()
        table = self.query_one("#searches-table", DataTable)
        table.clear()
        empty = self.query_one("#searches-empty", Static)
        if self._searches:
            empty.display = False
            table.display = True
            for name, state in self._searches:
                sort_label = f"{state.sort_by} {'↓' if state.sort_desc else '↑'}"
                table.add_row(name, state.source, state.keywords or "—", sort_label)
        else:
            empty.display = True
            table.display = False

    def action_apply(self) -> None:
        table = self.query_one("#searches-table", DataTable)
        if table.cursor_row < len(self._searches):
            _, state = self._searches[table.cursor_row]
            self.post_message(self.SearchApplied(state))

    def action_delete(self) -> None:
        table = self.query_one("#searches-table", DataTable)
        if table.cursor_row < len(self._searches):
            name, _ = self._searches[table.cursor_row]
            self._store.delete_search(name)
            self.reload()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "searches-apply":
            self.action_apply()
        elif event.button.id == "searches-delete":
            self.action_delete()
