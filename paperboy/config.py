"""Configuration loading from TOML file with built-in defaults."""
from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel


CONFIG_PATH = Path.home() / ".config" / "paperboy" / "config.toml"


class ArxivConfig(BaseModel):
    categories: list[str] = ["physics.plasm-ph", "cs.LG"]
    keywords: list[str] = []
    query: str = ""
    limit: int = 50


class OpenReviewVenueConfig(BaseModel):
    id: str
    keywords: list[str] = []


class OpenReviewConfig(BaseModel):
    venues: list[OpenReviewVenueConfig] = [
        OpenReviewVenueConfig(id="NeurIPS.cc/2025/Conference"),
        OpenReviewVenueConfig(id="ICML.cc/2025/Conference"),
    ]
    limit: int = 50


class JournalConfig(BaseModel):
    name: str
    feed_url: str
    keywords: list[str] = []


class AppConfig(BaseModel):
    refresh_interval_minutes: int = 30
    max_papers: int = 200


class Config(BaseModel):
    arxiv: ArxivConfig = ArxivConfig()
    openreview: OpenReviewConfig = OpenReviewConfig()
    journals: list[JournalConfig] = [
        JournalConfig(
            name="Nuclear Fusion",
            feed_url="https://iopscience.iop.org/journal/rss/0029-5515",
        ),
        JournalConfig(
            name="IEEE Transactions on Plasma Science",
            feed_url="https://ieeexplore.ieee.org/rss/TOC23.XML",
        ),
    ]
    app: AppConfig = AppConfig()


def load_config(path: Path | None = None) -> Config:
    """Load configuration from TOML file, falling back to defaults."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return Config()

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    return Config.model_validate(raw)
