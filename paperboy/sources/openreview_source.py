"""OpenReview paper source using the openreview-py client."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from paperboy.models import Paper, SourceKind
from paperboy.sources.base import PaperSource

logger = logging.getLogger(__name__)


class OpenReviewSource(PaperSource):
    """Fetches accepted papers from an OpenReview-hosted conference.

    Uses the openreview-py client (API v2) for public read access;
    no credentials required for publicly visible submissions.
    Keyword filtering is applied post-fetch on title and abstract.
    """

    kind = SourceKind.OPENREVIEW

    def __init__(
        self,
        venue_id: str,
        keywords: list[str] | None = None,
        client: Any | None = None,
    ) -> None:
        self._venue_id = venue_id
        self._keywords = keywords or []
        self._client = client
        self._name = self._friendly_name(venue_id)

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    async def fetch_latest(self, limit: int = 50) -> list[Paper]:
        """Fetch accepted submissions from the OpenReview venue."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._fetch_sync(limit))

    def _fetch_sync(self, limit: int) -> list[Paper]:
        try:
            client = self._client or self._make_client()
            notes = client.get_all_notes(
                invitation=f"{self._venue_id}/-/Submission",
                details="directReplies",
                limit=limit,
            )
            papers: list[Paper] = []
            for note in notes[:limit]:
                try:
                    p = self._note_to_paper(note)
                    if self._matches_keywords(p):
                        papers.append(p)
                except Exception as exc:
                    logger.warning(
                        "Failed to parse OpenReview note %s: %s",
                        getattr(note, "id", "?"),
                        exc,
                    )
            return papers
        except Exception as exc:
            logger.error("OpenReview fetch failed for %s: %s", self._venue_id, exc)
            raise

    def _matches_keywords(self, paper: Paper) -> bool:
        if not self._keywords:
            return True
        text = (paper.title + " " + paper.abstract).lower()
        return any(kw.lower() in text for kw in self._keywords)

    def _make_client(self) -> Any:
        import openreview
        return openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")

    def _note_to_paper(self, note: Any) -> Paper:
        content: dict[str, Any] = getattr(note, "content", {}) or {}

        def field(key: str) -> str:
            val = content.get(key, {})
            if isinstance(val, dict):
                return str(val.get("value", ""))
            return str(val) if val else ""

        title = field("title") or "Untitled"
        abstract = field("abstract") or ""

        authors_raw = content.get("authors", {})
        authors: list[str] = (
            list(authors_raw.get("value", []))
            if isinstance(authors_raw, dict)
            else list(authors_raw) if authors_raw else []
        )

        keywords_raw = content.get("keywords", {})
        categories: list[str] = (
            list(keywords_raw.get("value", []))
            if isinstance(keywords_raw, dict)
            else list(keywords_raw) if keywords_raw else []
        )

        note_id: str = getattr(note, "id", "") or ""
        pdf_path = field("pdf")
        pdf_url: str | None = f"https://openreview.net{pdf_path}" if pdf_path else None
        html_url: str | None = f"https://openreview.net/forum?id={note_id}" if note_id else None

        tcdate = getattr(note, "tcdate", None) or getattr(note, "cdate", None)
        published = self._ms_to_dt(tcdate)

        return Paper(
            id=f"openreview:{note_id}",
            title=title,
            authors=authors,
            abstract=abstract,
            source=self.name,
            kind=self.kind,
            published=published,
            venue=self._venue_id,
            pdf_url=pdf_url,
            html_url=html_url,
            categories=categories,
        )

    @staticmethod
    def _ms_to_dt(ms: int | float | None) -> datetime:
        if ms is None:
            return datetime.now(tz=timezone.utc)
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)

    @staticmethod
    def _friendly_name(venue_id: str) -> str:
        parts = venue_id.split("/")
        if len(parts) >= 2:
            org = parts[0].split(".")[0]
            year = parts[1] if len(parts) > 1 else ""
            return f"{org} {year}".strip()
        return venue_id
