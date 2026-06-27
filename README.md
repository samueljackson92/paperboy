# paperboy

A terminal RSS-style reader for academic papers from arXiv, OpenReview, and journals.

```
┌ Header ────────────────────────────────────────────────────────────────────┘
│ Unread: 12  |  Last refresh: 14:23:01 UTC                                     │
├────────────────────────────────────────────────────────────────────────────┤
│ ●  Scalable plasma control via RL    arXiv    Smith, J +2    2024-01-15  │
│ ●  Fusion ignition thresholds study   Nucl Fus  Wang, L       2024-01-14  │
│    Transformer scaling laws reviewed  NeurIPS   Brown, T +5   2024-01-13  │
│ ●  MHD equilibrium in tokamaks        arXiv    Lee, K        2024-01-12  │
└────────────────────────────────────────────────────────────────────────────┘
│ q quit  r refresh  f filter  o open PDF  enter open  space toggle read      │
└─ Footer ────────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
pip install -e .
# or with dev dependencies
pip install -e ".[dev]"
```

## Running the app

```bash
# Via console script
paperboy

# Or directly
python -m research_feed.app

# Via textual run (shows devtools)
textual run research_feed/app.py
```

## Configuration

Copy `config.toml` to `~/.config/paperboy/config.toml` and edit:

```toml
[arxiv]
categories = ["physics.plasm-ph", "cs.LG", "cs.AI"]
query = ""          # optional free-text filter
limit = 50

[openreview]
venues = ["NeurIPS.cc/2025/Conference"]
limit = 50

[[journals]]
name = "Nuclear Fusion"
feed_url = "https://iopscience.iop.org/journal/rss/0029-5515"

[[journals]]
name = "Nature"
feed_url = "https://www.nature.com/nature.rss"

[app]
refresh_interval_minutes = 30
max_papers = 200
```

If the file is absent, built-in defaults are used (`physics.plasm-ph`, `cs.LG`,
NeurIPS/ICML 2025, Nuclear Fusion, IEEE Trans. Plasma Science).

## Keybindings

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh all sources |
| `f` | Open source filter |
| `enter` | Open detail view (marks paper read) |
| `space` | Toggle read/unread |
| `o` | Open PDF in browser |
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `Esc` | Close modal |

## Running the tests

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

## Linting and type checking

```bash
# Lint and format
ruff check research_feed/ tests/
ruff format research_feed/ tests/

# Type checking
mypy research_feed/ tests/
```

## Package layout

```
research_feed/
  __init__.py
  models.py          — Paper dataclass, SourceKind enum
  config.py          — TOML config loading with defaults
  storage.py         — SQLite read/unread state persistence
  app.py             — Main Textual App
  research_feed.tcss — Catppuccin Mocha CSS theme
  sources/
    base.py            — PaperSource ABC
    arxiv_source.py    — arXiv Atom API client
    openreview_source.py — OpenReview API v2 client
    journal_source.py  — Generic RSS/Atom journal reader
    registry.py        — Concurrent source aggregator
  widgets/
    paper_list.py    — Filterable paper table
    detail_view.py   — Full-paper modal
    filter_panel.py  — Source filter picker
tests/
  test_models.py
  test_arxiv_source.py
  test_openreview_source.py
  test_journal_source.py
  test_registry.py
  test_storage.py
  test_app.py
```

## Adding a new paper source

1. Create `research_feed/sources/my_source.py`
2. Subclass `PaperSource` and implement `fetch_latest`:

```python
from research_feed.sources.base import PaperSource
from research_feed.models import Paper, SourceKind

class MySource(PaperSource):
    name = "My Journal"
    kind = SourceKind.JOURNAL

    async def fetch_latest(self, limit: int = 50) -> list[Paper]:
        # fetch and parse, return list[Paper]
        ...
```

3. Add an instance to `ResearchFeedApp._build_registry()` in `app.py`, or add a
   config entry under `[[journals]]` if it's an RSS/Atom feed (no code change needed).

## Architecture notes

- **Async-first**: all network I/O uses `httpx.AsyncClient` so Textual's asyncio
  event loop is never blocked. OpenReview's synchronous client is wrapped in
  `run_in_executor`.
- **Error isolation**: `SourceRegistry.fetch_all` uses `asyncio.gather(…,
  return_exceptions=True)` — one failing source logs an error but never crashes
  the UI or loses results from other sources.
- **Persistence**: read/unread state is stored in SQLite at
  `~/.local/share/paperboy/state.db`. The `ReadStateStore` interface is
  synchronous and lightweight; no ORM needed.
- **Rate limiting**: `ArxivSource` enforces arXiv's requested 3-second gap
  between requests using `asyncio.sleep`.
