"""Journal RSS/Atom feed source."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from research_feed.models import Paper, SourceKind
from research_feed.sources.base import PaperSource

logger = logging.getLogger(__name__)

_DC_NS = "http://purl.org/dc/elements/1.1/"
_ATOM_NS = "http://www.w3.org/2005/Atom"


class JournalSource(PaperSource):
    """Fetches latest articles from a journal RSS/Atom feed.

    The feed URL is a constructor parameter, enabling any journal that
    publishes RSS/Atom to be added without new code.
    """

    kind = SourceKind.JOURNAL

    def __init__(
        self,
        name: str,
        feed_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self._feed_url = feed_url
        self._client = client

    async def fetch_latest(self, limit: int = 50) -> list[Paper]:
        """Fetch latest articles from the journal RSS feed."""
        xml_text = await self._get_feed()
        return self._parse(xml_text, limit)

    async def _get_feed(self) -> str:
        headers = {"User-Agent": "paperboy/0.1 (academic feed reader)"}
        if self._client:
            resp = await self._client.get(self._feed_url, headers=headers)
            resp.raise_for_status()
            return resp.text
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(self._feed_url, headers=headers)
            resp.raise_for_status()
            return resp.text

    def _parse(self, xml_text: str, limit: int) -> list[Paper]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("Failed to parse feed XML for %s: %s", self.name, exc)
            return []

        items = root.findall(".//item")
        if not items:
            items = root.findall(f".//{{{_ATOM_NS}}}entry")

        papers: list[Paper] = []
        for item in items[:limit]:
            try:
                papers.append(self._item_to_paper(item))
            except Exception as exc:
                logger.warning("Failed to parse feed item for %s: %s", self.name, exc)
        return papers

    def _item_to_paper(self, item: ET.Element) -> Paper:
        def rss(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""

        def atom(tag: str) -> str:
            el = item.find(f"{{{_ATOM_NS}}}{tag}")
            return (el.text or "").strip() if el is not None else ""

        def dc(tag: str) -> str:
            el = item.find(f"{{{_DC_NS}}}{tag}")
            return (el.text or "").strip() if el is not None else ""

        title = rss("title") or atom("title") or "Untitled"
        link = rss("link") or atom("id") or ""
        abstract = rss("description") or atom("summary") or atom("content") or ""
        pub_date = rss("pubDate") or dc("date") or atom("published") or atom("updated")

        creator = dc("creator")
        if creator:
            authors = [a.strip() for a in creator.split(";") if a.strip()]
        else:
            raw_author = rss("author") or atom("author")
            authors = [raw_author] if raw_author else []

        published = self._parse_date(pub_date)
        paper_id = self.make_id(self.name.lower().replace(" ", "_"), link or title)

        identifier = dc("identifier")
        pdf_url: str | None = identifier if identifier and "doi" in identifier.lower() else None

        return Paper(
            id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            source=self.name,
            kind=self.kind,
            published=published,
            venue=self.name,
            pdf_url=pdf_url,
            html_url=link or None,
            categories=[],
        )

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        if not date_str:
            return datetime.now(tz=timezone.utc)
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            pass
        for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return datetime.now(tz=timezone.utc)


class NuclearFusionSource(JournalSource):
    """IOP Nuclear Fusion journal feed."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(
            name="Nuclear Fusion",
            feed_url="https://iopscience.iop.org/journal/rss/0029-5515",
            client=client,
        )


class IEEETransPlasmaScienceSource(JournalSource):
    """IEEE Transactions on Plasma Science feed."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(
            name="IEEE Trans. Plasma Science",
            feed_url="https://ieeexplore.ieee.org/rss/TOC23.XML",
            client=client,
        )
