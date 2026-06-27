"""Domain model for academic papers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

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
    is_bookmarked: bool = False
    citation_count: int | None = None
    semantic_scholar_id: str | None = None

    def with_read_state(self, is_read: bool) -> Paper:
        return self.model_copy(update={"is_read": is_read})

    def with_bookmark_state(self, is_bookmarked: bool) -> Paper:
        return self.model_copy(update={"is_bookmarked": is_bookmarked})


@dataclass
class FilterState:
    """Active filter + sort state for a PaperList."""

    source: str = "All"
    keywords: str = ""
    bookmarked_only: bool = False
    sort_by: Literal["date", "source", "title"] = "date"
    sort_desc: bool = True
