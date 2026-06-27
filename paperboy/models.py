"""Domain model for academic papers."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SourceKind(str, Enum):
    """Kind of paper source."""

    ARXIV = "arxiv"
    OPENREVIEW = "openreview"
    JOURNAL = "journal"


class Paper(BaseModel):
    """A single academic paper from any source."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str
    source: str
    kind: SourceKind
    published: datetime
    venue: str | None = None
    pdf_url: str | None = None
    html_url: str | None = None
    categories: list[str] = Field(default_factory=list)
    is_read: bool = False

    def with_read_state(self, is_read: bool) -> Paper:
        """Return a new Paper with updated read state."""
        return self.model_copy(update={"is_read": is_read})
