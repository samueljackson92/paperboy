"""Tests for ArxivSource with mocked HTTP."""
from __future__ import annotations

import httpx
import pytest

from research_feed.models import SourceKind
from research_feed.sources.arxiv_source import ArxivSource

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
    <category term="physics.flu-dyn" scheme="http://arxiv.org/schemas/atom"/>
    <link rel="alternate" type="text/html" href="https://arxiv.org/abs/2401.00001v1"/>
    <link rel="related" type="application/pdf" href="https://arxiv.org/pdf/2401.00001v1"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <title>Another Paper</title>
    <summary>Second abstract.</summary>
    <published>2024-01-14T00:00:00Z</published>
    <updated>2024-01-14T00:00:00Z</updated>
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


def _mock_client(body: str, status: int = 200) -> httpx.AsyncClient:
    transport = httpx.MockTransport(lambda req: httpx.Response(status, text=body))
    return httpx.AsyncClient(transport=transport)


@pytest.mark.asyncio
async def test_fetch_latest_parses_papers() -> None:
    src = ArxivSource(categories=["physics.plasm-ph"], client=_mock_client(SAMPLE_ATOM))
    src._last_request = 0.0

    papers = await src.fetch_latest(limit=10)

    assert len(papers) == 2
    assert papers[0].title == "Test Paper on Plasma Physics"
    assert papers[0].authors == ["Alice Smith", "Bob Jones"]
    assert papers[0].kind == SourceKind.ARXIV
    assert papers[0].source == "arXiv"
    assert "physics.plasm-ph" in papers[0].categories
    assert papers[0].pdf_url is not None
    assert "2401.00001" in papers[0].id


@pytest.mark.asyncio
async def test_fetch_latest_fallback_pdf_url() -> None:
    src = ArxivSource(categories=["cs.LG"], client=_mock_client(SAMPLE_ATOM))
    src._last_request = 0.0

    papers = await src.fetch_latest(limit=10)
    second = next(p for p in papers if "2401.00002" in p.id)
    assert second.pdf_url is not None
    assert "arxiv.org/pdf" in second.pdf_url


@pytest.mark.asyncio
async def test_fetch_latest_missing_date_uses_now() -> None:
    src = ArxivSource(client=_mock_client(MISSING_DATE_ATOM))
    src._last_request = 0.0

    papers = await src.fetch_latest(limit=10)
    assert len(papers) == 1
    assert papers[0].published is not None


@pytest.mark.asyncio
async def test_fetch_latest_http_error_raises() -> None:
    src = ArxivSource(client=_mock_client("", status=503))
    src._last_request = 0.0

    with pytest.raises(httpx.HTTPStatusError):
        await src.fetch_latest(limit=10)
