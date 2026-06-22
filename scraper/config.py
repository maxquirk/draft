"""Registry of every big-board source. run.py iterates this list; a source whose
module is missing or whose fetch() returns nothing is simply skipped and reported.
"""
from __future__ import annotations

from .base import SourceMeta

# module_attr is "<module under scraper.sources>"; each module exposes SOURCE + fetch().
SOURCES: list[tuple[str, SourceMeta]] = [
    ("mlb_pipeline", SourceMeta("mlb_pipeline", "MLB.com Pipeline",
        "https://www.mlb.com/news/top-200-draft-prospects-for-2026", "free", weight=1.2)),
    ("fangraphs", SourceMeta("fangraphs", "FanGraphs The Board",
        "https://www.fangraphs.com/prospects/the-board/2026-mlb-draft", "free", weight=1.3)),
    ("perfect_game", SourceMeta("perfect_game", "Perfect Game",
        "https://www.perfectgame.org/Articles/View.aspx?article=24219", "free", weight=1.0)),
    ("just_baseball", SourceMeta("just_baseball", "Just Baseball",
        "https://www.justbaseball.com/prospects/2026-mlb-draft-rankings/", "free", weight=1.0)),
    ("eleven_point7", SourceMeta("eleven_point7", "11Point7",
        "https://www.11point7.com/mlb-draft/2026-prospect-big-board", "free", weight=1.0)),
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
