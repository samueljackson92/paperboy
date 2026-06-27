"""Tests for SemanticScholarEnricher with mocked HTTP."""
import json
from datetime import datetime, timezone

import httpx
import pytest

from paperboy.models import Paper, SourceKind
from paperboy.sources.semantic_scholar import SemanticScholarEnricher


def _arxiv_paper(idx: int = 1) -> Paper:
    return Paper(
        id=f"arxiv:2401.0000{idx}",
        title=f"Paper {idx}",
        authors=["A. Author"],
        abstract="Abstract.",
        source="arXiv",
        kind=SourceKind.ARXIV,
        published=datetime(2024, 1, idx, tzinfo=timezone.utc),
    )


def _journal_paper() -> Paper:
    return Paper(
        id="nuclear_fusion:abc123",
        title="Journal Paper",
        authors=["B. Author"],
        abstract="Abstract.",
        source="Nuclear Fusion",
        kind=SourceKind.JOURNAL,
        published=datetime(2024, 1, 5, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_enrich_citations_populates_count() -> None:
    batch_response = [
        {"paperId": "s2id_001", "citationCount": 42, "externalIds": {"ArXiv": "2401.00001"}},
    ]
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=json.dumps(batch_response).encode())
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    papers = [_arxiv_paper(1)]
    result = await enricher.enrich_citations(papers)
    assert result[0].citation_count == 42
    assert result[0].semantic_scholar_id == "s2id_001"


@pytest.mark.asyncio
async def test_enrich_skips_non_arxiv() -> None:
    """Non-arXiv papers should pass through unchanged."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=b"[]")
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    paper = _journal_paper()
    result = await enricher.enrich_citations([paper])
    assert result[0].citation_count is None


@pytest.mark.asyncio
async def test_enrich_api_error_returns_unchanged() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(500, content=b"error")
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    papers = [_arxiv_paper(1)]
    result = await enricher.enrich_citations(papers)
    assert result[0].citation_count is None


@pytest.mark.asyncio
async def test_fetch_related_no_s2_id_returns_empty() -> None:
    enricher = SemanticScholarEnricher(api_key="test-key")
    paper = _arxiv_paper(1)  # no semantic_scholar_id
    result = await enricher.fetch_related(paper)
    assert result == []


@pytest.mark.asyncio
async def test_fetch_related_returns_list() -> None:
    rec_response = {
        "recommendedPapers": [
            {"title": "Related Work", "authors": [{"name": "C. Author"}], "year": 2023,
             "externalIds": {"ArXiv": "2301.00001"}},
        ]
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=json.dumps(rec_response).encode())
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    paper = _arxiv_paper(1).model_copy(update={"semantic_scholar_id": "s2id_001"})
    result = await enricher.fetch_related(paper, limit=1)
    assert len(result) == 1
    assert result[0]["title"] == "Related Work"
    assert "arxiv.org" in result[0]["url"]
