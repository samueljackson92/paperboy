"""Detail pane widget showing the currently highlighted paper."""
from __future__ import annotations

import webbrowser

from textual import work
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown, Static

from paperboy.latex import strip_latex
from paperboy.models import Paper


class DetailView(Widget):
    """Persistent bottom pane showing abstract and metadata for the highlighted paper."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._current_paper: Paper | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="detail-title")
        yield Static("", id="detail-authors")
        yield Static("", id="detail-meta")
        yield Markdown("", id="detail-markdown")
        yield Static("", id="related-list")

    def show_paper(self, paper: Paper) -> None:
        self._current_paper = paper
        authors_str = ", ".join(paper.authors) if paper.authors else "Unknown"
        date_str = paper.published.strftime("%Y-%m-%d")
        meta_parts = [paper.source, date_str]
        if paper.venue and paper.venue != paper.source:
            meta_parts.insert(1, paper.venue)
        if paper.categories:
            meta_parts.append(", ".join(paper.categories))
        if paper.citation_count is not None:
            meta_parts.append(f"{paper.citation_count} citations")

        self.query_one("#detail-title", Static).update(paper.title)
        self.query_one("#detail-authors", Static).update(authors_str)
        self.query_one("#detail-meta", Static).update(" · ".join(meta_parts))
        self.query_one("#detail-markdown", Markdown).update(
            strip_latex(paper.abstract) if paper.abstract else "_No abstract available._"
        )
        self.query_one("#related-list", Static).update("")
        self._load_related(paper)

    @work(exclusive=True)
    async def _load_related(self, paper: Paper) -> None:
        enricher = getattr(self.app, "_enricher", None)
        if enricher is None or not paper.semantic_scholar_id:
            return
        related = await enricher.fetch_related(paper)
        if not related or paper is not self._current_paper:
            return
        lines = ["**Related papers:**"]
        for r in related:
            title = r.get("title", "")
            year = f" ({r['year']})" if r.get("year") else ""
            url = r.get("url", "")
            if url:
                lines.append(f"- [{title}{year}]({url})")
            else:
                lines.append(f"- {title}{year}")
        self.query_one("#related-list", Static).update("\n".join(lines))

    def open_pdf(self) -> None:
        paper = self._current_paper
        if paper is None:
            return
        url = paper.pdf_url or paper.html_url
        if url:
            webbrowser.open(url)
        else:
            self.app.notify("No URL available for this paper", severity="warning", timeout=2)
