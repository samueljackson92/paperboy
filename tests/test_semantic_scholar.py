"""Tests for SemanticScholarEnricher with mocked HTTP."""
import json
from datetime import datetime, timezone

import httpx
import pytest

from paperboy.models import Paper, SourceKind
from paperboy.sources.semantic_scholar import SemanticScholarEnricher, _normalise


def _arxiv_paper(idx: int = 1) -> Paper:
    return Paper(
        id=f"arxiv:2401.0000{idx}",
        title=f"Attention Is All You Need Paper {idx}",
        authors=["A. Author"],
        abstract="Abstract.",
        source="arXiv",
        kind=SourceKind.ARXIV,
        published=datetime(2024, 1, idx, tzinfo=timezone.utc),
    )


def _journal_paper(title: str = "Plasma Confinement in Compact Tokamaks") -> Paper:
    return Paper(
        id="nuclear_fusion:abc123",
        title=title,
        authors=["B. Author"],
        abstract="Abstract.",
        source="Nuclear Fusion",
        kind=SourceKind.JOURNAL,
        published=datetime(2024, 1, 5, tzinfo=timezone.utc),
    )


def _openreview_paper(title: str = "Graph Neural Networks for Molecular Property Prediction") -> Paper:
    return Paper(
        id="openreview:abc123",
        title=title,
        authors=["C. Author"],
        abstract="Abstract.",
        source="NeurIPS 2024",
        kind=SourceKind.OPENREVIEW,
        published=datetime(2024, 1, 5, tzinfo=timezone.utc),
    )


# ── normalise helper ─────────────────────────────────────────────────────────

def test_normalise_strips_punctuation():
    assert _normalise("Hello, World!") == "hello world"


def test_normalise_lowercase():
    assert _normalise("UPPER") == "upper"


# ── arXiv batch enrichment ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrich_citations_arxiv_populates_count() -> None:
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
async def test_enrich_arxiv_api_error_returns_unchanged() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(500, content=b"error")
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    papers = [_arxiv_paper(1)]
    result = await enricher.enrich_citations(papers)
    assert result[0].citation_count is None


# ── title-search enrichment (journal / OpenReview) ──────────────────────────

def _title_search_transport(title: str, paper_id: str, citation_count: int) -> httpx.MockTransport:
    search_response = {
        "data": [{"paperId": paper_id, "citationCount": citation_count, "title": title, "externalIds": {}}]
    }
    return httpx.MockTransport(
        lambda req: httpx.Response(200, content=json.dumps(search_response).encode())
    )


@pytest.mark.asyncio
async def test_enrich_journal_via_title_search() -> None:
    paper = _journal_paper("Plasma Confinement in Compact Tokamaks")
    transport = _title_search_transport(
        title="Plasma Confinement in Compact Tokamaks",
        paper_id="s2_journal_001",
        citation_count=99,
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    result = await enricher.enrich_citations([paper])
    assert result[0].citation_count == 99
    assert result[0].semantic_scholar_id == "s2_journal_001"


@pytest.mark.asyncio
async def test_enrich_openreview_via_title_search() -> None:
    paper = _openreview_paper("Graph Neural Networks for Molecular Property Prediction")
    transport = _title_search_transport(
        title="Graph Neural Networks for Molecular Property Prediction",
        paper_id="s2_or_001",
        citation_count=212,
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    result = await enricher.enrich_citations([paper])
    assert result[0].citation_count == 212
    assert result[0].semantic_scholar_id == "s2_or_001"


@pytest.mark.asyncio
async def test_enrich_title_match_too_weak_returns_unchanged() -> None:
    """If S2 returns a very different title, the paper should be unchanged."""
    paper = _journal_paper("Plasma Physics Studies")
    search_response = {
        "data": [{"paperId": "s2_other", "citationCount": 5, "title": "Completely Different Topic", "externalIds": {}}]
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=json.dumps(search_response).encode())
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    result = await enricher.enrich_citations([paper])
    assert result[0].citation_count is None
    assert result[0].semantic_scholar_id is None


@pytest.mark.asyncio
async def test_enrich_title_search_empty_result_returns_unchanged() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=json.dumps({"data": []}).encode())
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    paper = _journal_paper()
    result = await enricher.enrich_citations([paper])
    assert result[0].citation_count is None


@pytest.mark.asyncio
async def test_enrich_mixed_arxiv_and_journal() -> None:
    """arXiv uses batch; journal uses title search. Both should be enriched."""
    arxiv = _arxiv_paper(1)
    journal = _journal_paper("Plasma Confinement in Compact Tokamaks")

    def handler(req: httpx.Request) -> httpx.Response:
        if "batch" in str(req.url):
            return httpx.Response(200, content=json.dumps([
                {"paperId": "s2_arxiv", "citationCount": 10, "externalIds": {"ArXiv": "2401.00001"}}
            ]).encode())
        return httpx.Response(200, content=json.dumps({
            "data": [{"paperId": "s2_journal", "citationCount": 20,
                      "title": "Plasma Confinement in Compact Tokamaks", "externalIds": {}}]
        }).encode())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    result = await enricher.enrich_citations([arxiv, journal])
    by_id = {p.id: p for p in result}
    assert by_id[arxiv.id].citation_count == 10
    assert by_id[journal.id].citation_count == 20


# ── related papers ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_related_no_s2_id_returns_empty() -> None:
    enricher = SemanticScholarEnricher(api_key="test-key")
    result = await enricher.fetch_related(_arxiv_paper(1))
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


@pytest.mark.asyncio
async def test_fetch_related_doi_url_for_non_arxiv() -> None:
    rec_response = {
        "recommendedPapers": [
            {"title": "DOI Paper", "authors": [], "year": 2022,
             "externalIds": {"DOI": "10.1234/test"}},
        ]
    }
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=json.dumps(rec_response).encode())
    )
    client = httpx.AsyncClient(transport=transport)
    enricher = SemanticScholarEnricher(api_key="test-key", client=client)

    paper = _journal_paper().model_copy(update={"semantic_scholar_id": "s2_journal"})
    result = await enricher.fetch_related(paper)
    assert "doi.org/10.1234/test" in result[0]["url"]
