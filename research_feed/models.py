"""Domain model for academic papers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SourceKind(str, Enum):
    """Kind of paper source."""

    ARXIV = "arxiv"
    OPENREVIEW = "openreview"
    JOURNAL = "journal"


@dataclass(frozen=True)
class Paper:
    """A single academic paper from any source."""

    id: str
    title: str
    authors: list[str]
    abstract: str
    source: str
    kind: SourceKind
    published: datetime
    venue: str | None = None
    pdf_url: str | None = None
    html_url: str | None = None
    categories: list[str] = field(default_factory=list)
    is_read: bool = False

    def with_read_state(self, is_read: bool) -> Paper:
        """Return a new Paper with updated read state."""
        return Paper(
            id=self.id,
            title=self.title,
            authors=self.authors,
            abstract=self.abstract,
            source=self.source,
            kind=self.kind,
            published=self.published,
            venue=self.venue,
            pdf_url=self.pdf_url,
            html_url=self.html_url,
            categories=self.categories,
            is_read=is_read,
        )
