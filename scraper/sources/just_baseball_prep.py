"""Just Baseball — 2026 Top 100 PREP (high-school) prospects.

Just Baseball splits its board into a college list and a prep list (see
just_baseball.py). The college list misses every HS player (Grady Emerson,
Jacob Lombard, ...), so this registers the prep list as its own source to
restore that coverage. Reuses the sibling adapter's parser — no new scraping.
"""
from __future__ import annotations

from ..base import SourceMeta
from .just_baseball import fetch_prep

SOURCE = SourceMeta(
    key="just_baseball_prep",
    name="Just Baseball Top 100 Prep",
    url="https://www.justbaseball.com/mlb-draft/2026-mlb-draft-top-prep-prospects/",
    access="free",
    weight=1.0,
)


def fetch() -> list[dict]:
    rows = fetch_prep()
    for r in rows:
        r["source"] = SOURCE.key
    return rows
