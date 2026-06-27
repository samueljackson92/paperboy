"""Semantic Scholar API enrichment — citation counts and related papers."""
from __future__ import annotations

import logging

import httpx

from paperboy.models import Paper

logger = logging.getLogger(__name__)

_BASE = "https://api.semanticscholar.org"


class SemanticScholarEnricher:
    """Enriches papers with citation counts and fetches related papers via S2 API."""

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client
        self._owns_client = client is None

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._api_key:
            h["x-api-key"] = self._api_key
        return h

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def enrich_citations(self, papers: list[Paper]) -> list[Paper]:
        """Batch-fetch citation counts for arXiv papers; return updated list."""
        arxiv_papers = {p.id: p for p in papers if p.id.startswith("arxiv:")}
        if not arxiv_papers:
            return papers

        s2_ids = [f"ArXiv:{pid[len('arxiv:'):]}" for pid in arxiv_papers]

        try:
            client = await self._get_client()
            resp = await client.post(
                f"{_BASE}/graph/v1/paper/batch",
                params={"fields": "citationCount,externalIds,paperId"},
                json={"ids": s2_ids},
                headers=self._headers(),
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Semantic Scholar batch fetch failed: %s", exc)
            return papers

        results: list[dict] = resp.json()
        enriched: dict[str, Paper] = {}
        for item in results:
            if item is None:
                continue
            arxiv_id = None
            ext_ids = item.get("externalIds") or {}
            if "ArXiv" in ext_ids:
                arxiv_id = f"arxiv:{ext_ids['ArXiv']}"
            if arxiv_id and arxiv_id in arxiv_papers:
                p = arxiv_papers[arxiv_id]
                enriched[arxiv_id] = p.model_copy(update={
                    "citation_count": item.get("citationCount"),
                    "semantic_scholar_id": item.get("paperId"),
                })

        return [enriched.get(p.id, p) for p in papers]

    async def fetch_related(self, paper: Paper, limit: int = 5) -> list[dict]:
        """Return up to `limit` related papers as plain dicts for display."""
        if not paper.semantic_scholar_id:
            return []
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{_BASE}/recommendations/v1/papers/forpaper/{paper.semantic_scholar_id}",
                params={"fields": "title,authors,year,externalIds", "limit": limit},
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("Related papers fetch failed: %s", exc)
            return []

        out = []
        for rec in data.get("recommendedPapers", [])[:limit]:
            ext = rec.get("externalIds") or {}
            url = ""
            if "ArXiv" in ext:
                url = f"https://arxiv.org/abs/{ext['ArXiv']}"
            authors = [a.get("name", "") for a in (rec.get("authors") or [])]
            out.append({
                "title": rec.get("title", ""),
                "authors": authors,
                "year": rec.get("year"),
                "url": url,
            })
        return out

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
