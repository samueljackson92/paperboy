"""In-terminal PDF viewer modal."""
from __future__ import annotations

import io
import logging
import re

import httpx
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, LoadingIndicator, Markdown, Static

from paperboy.models import Paper

logger = logging.getLogger(__name__)


class PDFView(ModalScreen[None]):
    """Modal screen that downloads a PDF and displays its extracted text."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    def __init__(self, paper: Paper) -> None:
        super().__init__()
        self._paper = paper

    def compose(self) -> ComposeResult:
        p = self._paper
        authors_preview = ", ".join(p.authors[:3])
        if len(p.authors) > 3:
            authors_preview += " et al."
        with Static(id="pdf-container"):
            yield Static(p.title, id="pdf-title")
            yield Static(authors_preview, id="pdf-authors")
            yield LoadingIndicator(id="pdf-loading")
            yield Markdown("", id="pdf-body")
            with Horizontal(id="pdf-actions"):
                yield Button("Close", id="pdf-close-btn", variant="default")

    def on_mount(self) -> None:
        self.query_one("#pdf-body", Markdown).display = False
        self._load()

    @work
    async def _load(self) -> None:
        pdf_url = self._paper.pdf_url
        if not pdf_url:
            self._show("_No PDF URL available for this paper._")
            return
        try:
            text = await _fetch_and_extract(pdf_url)
            self._show(text)
        except Exception as exc:
            logger.error("PDF load failed: %s", exc)
            self._show(f"**Error loading PDF**\n\n{exc}")

    def _show(self, content: str) -> None:
        self.query_one("#pdf-loading", LoadingIndicator).display = False
        body = self.query_one("#pdf-body", Markdown)
        body.update(content)
        body.display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pdf-close-btn":
            self.dismiss(None)


async def _fetch_and_extract(url: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf not installed — run: pip install pypdf")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    reader = PdfReader(io.BytesIO(resp.content))
    pages: list[str] = []
    for i, page in enumerate(reader.pages, 1):
        raw = (page.extract_text() or "").strip()
        if raw:
            pages.append(f"**— Page {i} —**\n\n{_clean(raw)}")

    return "\n\n---\n\n".join(pages) if pages else "_No text could be extracted from this PDF._"


def _clean(text: str) -> str:
    """Rejoin soft line-breaks from PDF extraction to improve readability."""
    # Join lines that are continuations (don't end with sentence-ending punctuation)
    text = re.sub(r"(?<![.!?:;,])\n(?!\n)", " ", text)
    # Collapse runs of spaces
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
