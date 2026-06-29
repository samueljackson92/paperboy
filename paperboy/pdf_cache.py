"""PDF download cache — avoids re-fetching the same PDF twice."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import httpx

_CACHE_DIR = Path(tempfile.gettempdir()) / "paperboy_pdf_cache"


async def fetch_pdf(url: str, client: httpx.AsyncClient) -> Path:
    """Return local path for the PDF at *url*, downloading it if necessary."""
    _CACHE_DIR.mkdir(exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    dest = _CACHE_DIR / f"{key}.pdf"
    if not dest.exists():
        resp = await client.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest
