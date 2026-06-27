"""Registry that aggregates results from all configured paper sources."""
from __future__ import annotations

import asyncio
import logging

from paperboy.models import Paper
from paperboy.sources.base import PaperSource

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Holds all configured PaperSource instances and fetches from them concurrently.

    One failing source does not block results from other sources.
    """

    def __init__(self, sources: list[PaperSource]) -> None:
        self._sources = sources

    @property
    def sources(self) -> list[PaperSource]:
        return list(self._sources)

    async def fetch_all(self, limit: int = 50) -> list[Paper]:
        """Fetch papers from all sources concurrently, sorted by published date."""
        tasks = [src.fetch_latest(limit) for src in self._sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_papers: list[Paper] = []
        for src, result in zip(self._sources, results):
            if isinstance(result, BaseException):
                logger.error("Source %r failed: %s", src.name, result)
            else:
                all_papers.extend(result)

        all_papers.sort(key=lambda p: p.published, reverse=True)
        return all_papers
