"""Semantic Scholar API enrichment — citation counts and related papers."""
from __future__ import annotations

import asyncio
import logging
import re

import httpx

from paperboy.models import Paper

logger = logging.getLogger(__name__)

_BASE = "https://api.semanticscholar.org"
_FIELDS = "citationCount,externalIds,paperId"


def _normalise(title: str) -> str:
    """Lowercase and strip punctuation for loose title comparison."""
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


class SemanticScholarEnricher:
    """Enriches papers with citation counts and fetches related papers via S2 API."""

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client
        self._owns_client = client is None
        # Conservative concurrency — S2 free tier allows ~1 req/s without key, ~10/s with
        self._sem = asyncio.Semaphore(5 if api_key else 1)

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._api_key:
            h["x-api-key"] = self._api_key
        return h

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    # ── arXiv: fast batch lookup ─────────────────────────────────────────

    async def _enrich_arxiv(self, arxiv_papers: dict[str, Paper]) -> dict[str, Paper]:
        s2_ids = [f"ArXiv:{pid[len('arxiv:'):]}" for pid in arxiv_papers]
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{_BASE}/graph/v1/paper/batch",
                params={"fields": _FIELDS},
                json={"ids": s2_ids},
                headers=self._headers(),
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("S2 arXiv batch fetch failed: %s", exc)
            return {}

        enriched: dict[str, Paper] = {}
        for item in resp.json():
            if item is None:
                continue
            ext_ids = item.get("externalIds") or {}
            if "ArXiv" in ext_ids:
                paper_id = f"arxiv:{ext_ids['ArXiv']}"
                if paper_id in arxiv_papers:
                    enriched[paper_id] = arxiv_papers[paper_id].model_copy(update={
                        "citation_count": item.get("citationCount"),
                        "semantic_scholar_id": item.get("paperId"),
                    })
        return enriched

    # ── Non-arXiv: title search ──────────────────────────────────────────

    async def _search_by_title(self, paper: Paper) -> Paper:
        """Look up a single paper by title; return enriched copy or original."""
        async with self._sem:
            try:
                client = await self._get_client()
                resp = await client.get(
                    f"{_BASE}/graph/v1/paper/search",
                    params={"query": paper.title, "fields": _FIELDS, "limit": 1},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.debug("S2 title search failed for '%s': %s", paper.title[:60], exc)
                return paper

        hits = data.get("data") or []
        if not hits:
            return paper

        hit = hits[0]
        # Guard against spurious matches — require normalised title to share at least
        # 80% of words with the query title.
        hit_title = _normalise(hit.get("title") or "")
        query_words = set(_normalise(paper.title).split())
        hit_words = set(hit_title.split())
        if not query_words:
            return paper
        overlap = len(query_words & hit_words) / len(query_words)
        if overlap < 0.8:
            logger.debug(
                "S2 title match too weak (%.0f%%) for '%s'", overlap * 100, paper.title[:60]
            )
            return paper

        return paper.model_copy(update={
            "citation_count": hit.get("citationCount"),
            "semantic_scholar_id": hit.get("paperId"),
        })

    # ── Public API ───────────────────────────────────────────────────────

    async def enrich_citations(self, papers: list[Paper]) -> list[Paper]:
        """Fetch citation counts for all papers; arXiv via batch, others via title search."""
        arxiv_papers = {p.id: p for p in papers if p.id.startswith("arxiv:")}
        other_papers = [p for p in papers if not p.id.startswith("arxiv:")]

        arxiv_enriched: dict[str, Paper] = {}
        if arxiv_papers:
            arxiv_enriched = await self._enrich_arxiv(arxiv_papers)

        other_enriched: dict[str, Paper] = {}
        if other_papers:
            tasks = [self._search_by_title(p) for p in other_papers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for original, result in zip(other_papers, results):
                if isinstance(result, Paper):
                    other_enriched[original.id] = result
                else:
                    logger.debug("Title search task error: %s", result)

        enriched = {**arxiv_enriched, **other_enriched}
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
            elif "DOI" in ext:
                url = f"https://doi.org/{ext['DOI']}"
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
