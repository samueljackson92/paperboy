"""Tests for JournalSource with mocked HTTP."""
from __future__ import annotations

import httpx
import pytest

from paperboy.models import SourceKind
from paperboy.sources.journal_source import JournalSource

RSS_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Nuclear Fusion</title>
    <item>
      <title>Plasma confinement study</title>
      <link>https://iopscience.iop.org/article/10.1088/1741-4326/test1</link>
      <description>We study plasma confinement in a tokamak.</description>
      <pubDate>Mon, 15 Jan 2024 00:00:00 GMT</pubDate>
      <dc:creator>Alice Smith; Bob Jones</dc:creator>
      <dc:identifier>https://doi.org/10.1088/1741-4326/test1</dc:identifier>
    </item>
    <item>
      <title>Fusion energy advances</title>
      <link>https://iopscience.iop.org/article/10.1088/1741-4326/test2</link>
      <description>Progress in fusion energy research.</description>
      <pubDate>Sun, 14 Jan 2024 00:00:00 GMT</pubDate>
      <dc:creator>Carol White</dc:creator>
    </item>
  </channel>
</rss>
"""

ATOM_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Journal</title>
  <entry>
    <id>https://example.com/article/1</id>
    <title>Atom Feed Article</title>
    <summary>An article from an Atom feed.</summary>
    <published>2024-01-15T00:00:00Z</published>
  </entry>
</feed>
"""


def _src(
    body: str,
    name: str = "Nuclear Fusion",
    status: int = 200,
    keywords: list[str] | None = None,
) -> JournalSource:
    transport = httpx.MockTransport(lambda req: httpx.Response(status, text=body))
    client = httpx.AsyncClient(transport=transport)
    return JournalSource(
        name=name,
        feed_url="https://example.com/rss",
        keywords=keywords,
        client=client,
    )


@pytest.mark.asyncio
async def test_fetch_rss_parses_items() -> None:
    src = _src(RSS_FEED)
    papers = await src.fetch_latest(limit=10)
    assert len(papers) == 2
    assert papers[0].title == "Plasma confinement study"
    assert papers[0].kind == SourceKind.JOURNAL
    assert papers[0].source == "Nuclear Fusion"
    assert papers[0].authors == ["Alice Smith", "Bob Jones"]
    assert papers[0].pdf_url is not None


@pytest.mark.asyncio
async def test_fetch_atom_parses_entries() -> None:
    src = _src(ATOM_FEED, name="Test Journal")
    papers = await src.fetch_latest(limit=10)
    assert len(papers) == 1
    assert papers[0].title == "Atom Feed Article"
    assert papers[0].abstract == "An article from an Atom feed."


@pytest.mark.asyncio
async def test_keyword_filter_matches() -> None:
    src = _src(RSS_FEED, keywords=["tokamak"])
    papers = await src.fetch_latest(limit=10)
    # Only the first item mentions tokamak
    assert len(papers) == 1
    assert "tokamak" in papers[0].abstract.lower()


@pytest.mark.asyncio
async def test_keyword_filter_none_match() -> None:
    src = _src(RSS_FEED, keywords=["quantum computing"])
    papers = await src.fetch_latest(limit=10)
    assert papers == []


@pytest.mark.asyncio
async def test_no_keywords_returns_all() -> None:
    src = _src(RSS_FEED, keywords=[])
    papers = await src.fetch_latest(limit=10)
    assert len(papers) == 2


@pytest.mark.asyncio
async def test_fetch_http_error_raises() -> None:
    src = _src("", status=404)
    with pytest.raises(httpx.HTTPStatusError):
        await src.fetch_latest(limit=10)


@pytest.mark.asyncio
async def test_fetch_malformed_xml_returns_empty() -> None:
    src = _src("<not valid xml")
    papers = await src.fetch_latest(limit=10)
    assert papers == []
