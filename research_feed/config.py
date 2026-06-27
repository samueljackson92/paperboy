"""Configuration loading from TOML file with built-in defaults."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "arxiv": {
        "categories": ["physics.plasm-ph", "cs.LG"],
        "query": "",
        "limit": 50,
    },
    "openreview": {
        "venues": [
            "NeurIPS.cc/2025/Conference",
            "ICML.cc/2025/Conference",
        ],
        "limit": 50,
    },
    "journals": [
        {
            "name": "Nuclear Fusion",
            "feed_url": "https://iopscience.iop.org/journal/rss/0029-5515",
        },
        {
            "name": "IEEE Transactions on Plasma Science",
            "feed_url": "https://ieeexplore.ieee.org/rss/TOC23.XML",
        },
    ],
    "app": {
        "refresh_interval_minutes": 30,
        "max_papers": 200,
    },
}

CONFIG_PATH = Path.home() / ".config" / "paperboy" / "config.toml"


@dataclass
class ArxivConfig:
    categories: list[str] = field(default_factory=lambda: ["physics.plasm-ph", "cs.LG"])
    query: str = ""
    limit: int = 50


@dataclass
class OpenReviewConfig:
    venues: list[str] = field(default_factory=lambda: [
        "NeurIPS.cc/2025/Conference",
        "ICML.cc/2025/Conference",
    ])
    limit: int = 50


@dataclass
class JournalConfig:
    name: str
    feed_url: str


@dataclass
class AppConfig:
    refresh_interval_minutes: int = 30
    max_papers: int = 200


@dataclass
class Config:
    arxiv: ArxivConfig = field(default_factory=ArxivConfig)
    openreview: OpenReviewConfig = field(default_factory=OpenReviewConfig)
    journals: list[JournalConfig] = field(default_factory=lambda: [
        JournalConfig("Nuclear Fusion", "https://iopscience.iop.org/journal/rss/0029-5515"),
        JournalConfig("IEEE Transactions on Plasma Science", "https://ieeexplore.ieee.org/rss/TOC23.XML"),
    ])
    app: AppConfig = field(default_factory=AppConfig)


def load_config(path: Path | None = None) -> Config:
    """Load configuration from TOML file, falling back to defaults."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return Config()

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    arxiv_raw = raw.get("arxiv", {})
    arxiv = ArxivConfig(
        categories=arxiv_raw.get("categories", DEFAULT_CONFIG["arxiv"]["categories"]),
        query=arxiv_raw.get("query", ""),
        limit=arxiv_raw.get("limit", 50),
    )

    or_raw = raw.get("openreview", {})
    openreview = OpenReviewConfig(
        venues=or_raw.get("venues", DEFAULT_CONFIG["openreview"]["venues"]),
        limit=or_raw.get("limit", 50),
    )

    journals_raw = raw.get("journals", DEFAULT_CONFIG["journals"])
    journals = [JournalConfig(j["name"], j["feed_url"]) for j in journals_raw]

    app_raw = raw.get("app", {})
    app = AppConfig(
        refresh_interval_minutes=app_raw.get("refresh_interval_minutes", 30),
        max_papers=app_raw.get("max_papers", 200),
    )

    return Config(arxiv=arxiv, openreview=openreview, journals=journals, app=app)
