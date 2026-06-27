"""Abstract base class for all paper sources."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from research_feed.models import Paper, SourceKind


class PaperSource(ABC):
    """Abstract base for a source that can fetch academic papers."""

    name: str
    kind: SourceKind

    @abstractmethod
    async def fetch_latest(self, limit: int = 50) -> list[Paper]:
        """Fetch the most recent papers from this source."""
        ...

    @staticmethod
    def make_id(namespace: str, raw_id: str) -> str:
        """Build a stable, namespaced paper ID."""
        digest = hashlib.sha256(f"{namespace}:{raw_id}".encode()).hexdigest()[:16]
        return f"{namespace}:{digest}"

    @staticmethod
    def normalize_datetime(dt: datetime | None) -> datetime:
        """Ensure datetime is timezone-aware (UTC) and not None."""
        if dt is None:
            return datetime.now(tz=timezone.utc)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
