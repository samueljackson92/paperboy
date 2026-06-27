"""Detail pane widget showing the currently highlighted paper."""
from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Markdown, Static

from paperboy.models import Paper


class DetailView(Widget):
    """Persistent bottom pane showing abstract and metadata for the highlighted paper."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._current_pdf_url: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="detail-title")
        yield Static("", id="detail-authors")
        yield Static("", id="detail-meta")
        yield Markdown("", id="detail-markdown")
        with Horizontal(id="detail-actions"):
            yield Button("Open PDF", id="pdf-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#detail-actions").display = False

    def show_paper(self, paper: Paper) -> None:
        authors_str = ", ".join(paper.authors) if paper.authors else "Unknown"
        date_str = paper.published.strftime("%Y-%m-%d")
        meta_parts = [paper.source, date_str]
        if paper.venue and paper.venue != paper.source:
            meta_parts.insert(1, paper.venue)
        if paper.categories:
            meta_parts.append(", ".join(paper.categories))

        self.query_one("#detail-title", Static).update(paper.title)
        self.query_one("#detail-authors", Static).update(authors_str)
        self.query_one("#detail-meta", Static).update(" · ".join(meta_parts))
        self.query_one("#detail-markdown", Markdown).update(
            paper.abstract or "_No abstract available._"
        )

        self._current_pdf_url = paper.pdf_url
        self.query_one("#detail-actions").display = bool(paper.pdf_url)

    def open_pdf(self) -> None:
        if self._current_pdf_url:
            webbrowser.open(self._current_pdf_url)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pdf-btn":
            self.open_pdf()
