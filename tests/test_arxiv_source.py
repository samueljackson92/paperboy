"""Tests for ArxivSource with mocked HTTP."""
from __future__ import annotations

import httpx
import pytest

from paperboy.models import SourceKind
from paperboy.sources.arxiv_source import ArxivSource

SAMPLE_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Test Paper on Plasma Physics</title>
    <summary>This is an abstract about plasma.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <updated>2024-01-15T00:00:00Z</updated>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <category term="physics.plasm-ph" scheme="http://arxiv.org/schemas/atom"/>
    <link rel="alternate" type="text/html" href="https://arxiv.org/abs/2401.00001v1"/>
    <link rel="related" type="application/pdf" href="https://arxiv.org/pdf/2401.00001v1"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <title>Another Paper</title>
    <summary>Second abstract.</summary>
    <published>2024-01-14T00:00:00Z</published>
    <author><name>Carol White</name></author>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
"""

MISSING_DATE_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.99999v1</id>
    <title>Paper With Missing Date</title>
    <summary>Abstract here.</summary>
    <author><name>Dave Brown</name></author>
  </entry>
</feed>
"""


def _src(body: str, status: int = 200, **kwargs: object) -> ArxivSource:
    transport = httpx.MockTransport(lambda req: httpx.Response(status, text=body))
    client = httpx.AsyncClient(transport=transport)
    src = ArxivSource(client=client, **kwargs)  # type: ignore[arg-type]
    src._last_request = 0.0
    return src


@pytest.mark.asyncio
async def test_fetch_latest_parses_papers() -> None:
    src = _src(SAMPLE_ATOM, categories=["physics.plasm-ph"])
    papers = await src.fetch_latest(limit=10)

    assert len(papers) == 2
    assert papers[0].title == "Test Paper on Plasma Physics"
    assert papers[0].authors == ["Alice Smith", "Bob Jones"]
    assert papers[0].kind == SourceKind.ARXIV
    assert papers[0].source == "arXiv"
    assert "physics.plasm-ph" in papers[0].categories
    assert "2401.00001" in papers[0].id


@pytest.mark.asyncio
async def test_fetch_latest_fallback_pdf_url() -> None:
    src = _src(SAMPLE_ATOM)
    papers = await src.fetch_latest(limit=10)
    second = next(p for p in papers if "2401.00002" in p.id)
    assert second.pdf_url is not None
    assert "arxiv.org/pdf" in second.pdf_url


@pytest.mark.asyncio
async def test_fetch_latest_missing_date_uses_now() -> None:
    src = _src(MISSING_DATE_ATOM)
    papers = await src.fetch_latest(limit=10)
    assert len(papers) == 1
    assert papers[0].published is not None


@pytest.mark.asyncio
async def test_fetch_latest_http_error_raises() -> None:
    src = _src("", status=503)
    with pytest.raises(httpx.HTTPStatusError):
        await src.fetch_latest(limit=10)


def test_build_query_categories_only() -> None:
    src = ArxivSource(categories=["cs.LG", "cs.AI"])
    assert src._build_query() == "cat:cs.LG OR cat:cs.AI"


def test_build_query_keywords_only() -> None:
    src = ArxivSource(categories=[], keywords=["plasma", "fusion"])
    q = src._build_query()
    assert "ti:plasma OR abs:plasma" in q
    assert "ti:fusion OR abs:fusion" in q


def test_build_query_categories_and_keywords() -> None:
    src = ArxivSource(categories=["physics.plasm-ph"], keywords=["tokamak"])
    q = src._build_query()
    assert "cat:physics.plasm-ph" in q
    assert "ti:tokamak OR abs:tokamak" in q
    # Both parts must be ANDed
    assert " AND " in q
