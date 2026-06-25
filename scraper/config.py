"""Registry of every big-board source. run.py iterates this list; a source whose
module is missing or whose fetch() returns nothing is simply skipped and reported.
"""
from __future__ import annotations

from .base import SourceMeta

# module_attr is "<module under scraper.sources>"; each module exposes SOURCE + fetch().
SOURCES: list[tuple[str, SourceMeta]] = [
    ("mlb_pipeline", SourceMeta("mlb_pipeline", "MLB.com Pipeline",
        "https://www.mlb.com/news/top-200-draft-prospects-for-2026", "free", weight=1.2)),
    ("just_baseball", SourceMeta("just_baseball", "Just Baseball",
        "https://www.justbaseball.com/mlb-draft/mlb-draft-top-college-prospects/", "free", weight=1.0)),
    ("espn_mcdaniel", SourceMeta("espn_mcdaniel", "ESPN / Kiley McDaniel",
        "https://www.espn.com/mlb/story/_/id/48778463/2026-mlb-draft-rankings-update-top-150-prospects",
        "paywall", weight=1.4)),
    ("keith_law", SourceMeta("keith_law", "The Athletic / Keith Law",
        "https://www.nytimes.com/athletic/baseball/mlb-draft/", "paywall", weight=1.4)),
    ("baseball_america", SourceMeta("baseball_america", "Baseball America",
        "https://www.baseballamerica.com/rankings/2026-top-mlb-draft-prospects/", "paywall", weight=1.4)),
]

SOURCE_WEIGHTS = {key: meta.weight for key, meta in SOURCES}
SOURCE_NAMES = {key: meta.name for key, meta in SOURCES}
SOURCE_ACCESS = {key: meta.access for key, meta in SOURCES}
