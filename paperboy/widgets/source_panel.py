"""Left sidebar listing all sources for quick filtering."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class SourcePanel(Widget):
    """Sidebar listing available sources; posts SourceSelected on navigation."""

    class SourceSelected(Message):
        def __init__(self, source: str) -> None:
            super().__init__()
            self.source = source

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._sources: list[str] = []
        self._unread: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        yield OptionList(id="source-option-list")

    def on_mount(self) -> None:
        self._rebuild()

    def set_sources(self, sources: list[str], unread_counts: dict[str, int] | None = None) -> None:
        self._sources = list(sources)
        self._unread = unread_counts or {}
        self._rebuild()

    def _rebuild(self) -> None:
        ol = self.query_one(OptionList)
        ol.clear_options()
        total = sum(self._unread.values())
        ol.add_option(Option(f"All ({total})" if total else "All", id="All"))
        for s in self._sources:
            count = self._unread.get(s, 0)
            ol.add_option(Option(f"{s} ({count})" if count else s, id=s))
        ol.highlighted = 0

    def set_active_source(self, source: str) -> None:
        """Sync the sidebar highlight to match an externally applied filter."""
        options = ["All"] + self._sources
        try:
            self.query_one(OptionList).highlighted = options.index(source)
        except ValueError:
            self.query_one(OptionList).highlighted = 0

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self.post_message(self.SourceSelected(str(event.option.id)))
