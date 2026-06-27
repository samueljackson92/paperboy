"""Detail view modal for a single paper."""
from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, Static

from paperboy.models import Paper
from paperboy.widgets.pdf_view import PDFView


class DetailView(ModalScreen[None]):
    """Modal screen showing full paper details."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", show=True),
        Binding("q", "dismiss_modal", "Close", show=False),
        Binding("o", "open_pdf", "Open PDF", show=True),
    ]

    def __init__(self, paper: Paper) -> None:
        super().__init__()
        self._paper = paper

    def compose(self) -> ComposeResult:
        p = self._paper
        authors_str = ", ".join(p.authors) if p.authors else "Unknown"
        date_str = p.published.strftime("%Y-%m-%d")
        meta_parts = [p.source, date_str]
        if p.venue and p.venue != p.source:
            meta_parts.insert(1, p.venue)
        if p.categories:
            meta_parts.append(", ".join(p.categories))

        with Static(id="detail-container"):
            yield Static(p.title, id="detail-title")
            yield Static(authors_str, id="detail-authors")
            yield Static(" · ".join(meta_parts), id="detail-meta")
            yield Markdown(p.abstract or "_No abstract available._", id="detail-markdown")
            with Horizontal(id="detail-actions"):
                yield Button("Close", id="close-btn", variant="default")
                if p.pdf_url:
                    yield Button("View PDF", id="view-pdf-btn")
                    yield Button("Browser", id="pdf-btn", variant="primary")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def action_open_pdf(self) -> None:
        if self._paper.pdf_url:
            webbrowser.open(self._paper.pdf_url)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss(None)
        elif event.button.id == "view-pdf-btn":
            self.app.push_screen(PDFView(self._paper))
        elif event.button.id == "pdf-btn":
            self.action_open_pdf()
