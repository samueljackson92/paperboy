"""arXiv paper source using the official Atom API."""
from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx

from research_feed.models import Paper, SourceKind
from research_feed.sources.base import PaperSource

logger = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}
_RATE_LIMIT_SECS = 3.0


class ArxivSource(PaperSource):
    """Fetches papers from arXiv using the public Atom API.

    Respects arXiv's stated rate limit of one request every 3 seconds.
    """

    name = "arXiv"
    kind = SourceKind.ARXIV

    def __init__(
        self,
        categories: list[str] | None = None,
        query: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._categories = categories or ["physics.plasm-ph", "cs.LG"]
        self._query = query
        self._client = client
        self._last_request: float = 0.0

    async def fetch_latest(self, limit: int = 50) -> list[Paper]:
        """Fetch latest papers for configured arXiv categories."""
        search_query = self._build_query()
        params: dict[str, Any] = {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        await self._throttle()
        xml_text = await self._get(params)
        return self._parse(xml_text)

    def _build_query(self) -> str:
        cat_query = " OR ".join(f"cat:{c}" for c in self._categories)
        if self._query:
            return f"({cat_query}) AND ({self._query})"
        return cat_query

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < _RATE_LIMIT_SECS:
            await asyncio.sleep(_RATE_LIMIT_SECS - elapsed)
        self._last_request = time.monotonic()

    async def _get(self, params: dict[str, Any]) -> str:
        if self._client:
            resp = await self._client.get(ARXIV_API, params=params)
            resp.raise_for_status()
            return resp.text
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(ARXIV_API, params=params)
            resp.raise_for_status()
            return resp.text

    def _parse(self, xml_text: str) -> list[Paper]:
        root = ET.fromstring(xml_text)
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", NS):
            try:
                papers.append(self._entry_to_paper(entry))
            except Exception as exc:
                logger.warning("Failed to parse arXiv entry: %s", exc)
        return papers

    def _entry_to_paper(self, entry: ET.Element) -> Paper:
        def text(tag: str) -> str:
            el = entry.find(tag, NS)
            return (el.text or "").strip() if el is not None else ""

        arxiv_id = text("atom:id").split("/abs/")[-1]
        title = " ".join(text("atom:title").split())
        abstract = " ".join(text("atom:summary").split())
        published_str = text("atom:published")
        updated_str = text("atom:updated")
        published = self._parse_date(published_str or updated_str)

        authors = [
            " ".join((a.find("atom:name", NS).text or "").split())
            for a in entry.findall("atom:author", NS)
            if a.find("atom:name", NS) is not None
        ]

        categories = [
            c.get("term", "")
            for c in entry.findall("atom:category", NS)
        ]

        pdf_url: str | None = None
        html_url: str | None = None
        for link in entry.findall("atom:link", NS):
            rel = link.get("rel", "")
            href = link.get("href", "")
            link_type = link.get("type", "")
            if rel == "related" and "pdf" in link_type:
                pdf_url = href
            elif rel == "alternate":
                html_url = href
            elif "pdf" in href and pdf_url is None:
                pdf_url = href

        if pdf_url is None and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        if html_url is None and arxiv_id:
            html_url = f"https://arxiv.org/abs/{arxiv_id}"

        return Paper(
            id=f"arxiv:{arxiv_id}",
            title=title,
            authors=authors,
            abstract=abstract,
            source=self.name,
            kind=self.kind,
            published=published,
            venue=None,
            pdf_url=pdf_url,
            html_url=html_url,
            categories=categories,
        )

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        formats = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return datetime.now(tz=timezone.utc)
