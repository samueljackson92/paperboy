"""Detail view modal for a single paper."""
from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, Static

from paperboy.models import Paper


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
        cats_str = ", ".join(p.categories) if p.categories else "—"
        venue_str = p.venue or "—"
        date_str = p.published.strftime("%Y-%m-%d")
        content = f"""# {p.title}

**Authors:** {authors_str}

**Source:** {p.source} | **Venue:** {venue_str} | **Date:** {date_str}

**Categories:** {cats_str}

---

## Abstract

{p.abstract or '_No abstract available._'}

---

**PDF:** {p.pdf_url or '—'}  
**URL:** {p.html_url or '—'}
"""
        with Static(id="detail-container"):
            yield Markdown(content, id="detail-markdown")
            yield Button("Close [Esc]", id="close-btn", variant="default")
            if p.pdf_url:
                yield Button("Open PDF [o]", id="pdf-btn", variant="primary")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def action_open_pdf(self) -> None:
        if self._paper.pdf_url:
            webbrowser.open(self._paper.pdf_url)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss(None)
        elif event.button.id == "pdf-btn":
            self.action_open_pdf()
