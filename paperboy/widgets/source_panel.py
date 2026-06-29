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

    def compose(self) -> ComposeResult:
        yield OptionList(id="source-option-list")

    def on_mount(self) -> None:
        self._rebuild(["All"])

    def set_sources(self, sources: list[str]) -> None:
        self._sources = list(sources)
        self._rebuild(["All"] + self._sources)

    def _rebuild(self, options: list[str]) -> None:
        ol = self.query_one(OptionList)
        ol.clear_options()
        for s in options:
            ol.add_option(Option(s, id=s))
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
