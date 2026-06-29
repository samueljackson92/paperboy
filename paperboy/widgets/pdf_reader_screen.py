"""Full-screen in-app PDF reader."""
from __future__ import annotations

import io

import fitz  # pymupdf
import httpx
from PIL import Image as PilImage
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, Static
from textual_image.widget import Image as TxImage

from paperboy.models import Paper
from paperboy.pdf_cache import fetch_pdf


class PdfReaderScreen(ModalScreen[None]):
    """Full-screen PDF reader: downloads, extracts text + images, renders inline."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Scroll up", show=False),
        Binding("ctrl+d", "page_down", "Page down", show=False),
        Binding("ctrl+u", "page_up", "Page up", show=False),
    ]

    def __init__(self, paper: Paper) -> None:
        super().__init__()
        self._paper = paper

    def compose(self) -> ComposeResult:
        with Vertical(id="pdf-outer"):
            yield Static(self._paper.title[:100], id="pdf-title")
            yield Static("Downloading…", id="pdf-status")
            with VerticalScroll(id="pdf-scroll"):
                pass

    def on_mount(self) -> None:
        self._fetch()

    @work(exclusive=True)
    async def _fetch(self) -> None:
        url = self._paper.pdf_url or self._paper.html_url
        if not url:
            self.query_one("#pdf-status", Static).update("No PDF URL available for this paper.")
            return

        status = self.query_one("#pdf-status", Static)
        try:
            async with httpx.AsyncClient() as client:
                path = await fetch_pdf(url, client)
        except Exception as exc:
            status.update(f"Download failed: {exc}")
            return

        status.update("Rendering…")
        scroll = self.query_one("#pdf-scroll", VerticalScroll)
        try:
            doc = fitz.open(str(path))
        except Exception as exc:
            status.update(f"Could not open PDF: {exc}")
            return

        for page_num, page in enumerate(doc):
            # ── text ────────────────────────────────────────────────────────
            text = page.get_text("text").strip()
            if text:
                await scroll.mount(Markdown(text, id=f"page-text-{page_num}"))

            # ── images ──────────────────────────────────────────────────────
            for img_idx, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    if pix.width < 10 or pix.height < 10:
                        continue  # skip tiny decorative images
                    pil_img = PilImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    # cap render width to avoid giant images overwhelming the terminal
                    max_w = 800
                    if pil_img.width > max_w:
                        ratio = max_w / pil_img.width
                        pil_img = pil_img.resize(
                            (max_w, int(pil_img.height * ratio)), PilImage.LANCZOS
                        )
                    await scroll.mount(
                        TxImage(pil_img, id=f"img-p{page_num}-{img_idx}")
                    )
                except Exception:
                    continue  # skip unrenderable images silently

        doc.close()
        status.update(f"  {len(doc) if hasattr(doc, '__len__') else '?'} pages  ·  ESC to close")
        # Re-open to get page count after close
        doc2 = fitz.open(str(path))
        status.update(f"  {len(doc2)} pages  ·  ESC to close")
        doc2.close()

    def action_scroll_down(self) -> None:
        self.query_one("#pdf-scroll", VerticalScroll).scroll_down(animate=False)

    def action_scroll_up(self) -> None:
        self.query_one("#pdf-scroll", VerticalScroll).scroll_up(animate=False)

    def action_page_down(self) -> None:
        self.query_one("#pdf-scroll", VerticalScroll).scroll_page_down(animate=False)

    def action_page_up(self) -> None:
        self.query_one("#pdf-scroll", VerticalScroll).scroll_page_up(animate=False)
