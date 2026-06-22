"""The Athletic — Keith Law's 2026 MLB draft big board (top 100).

The article prose is gated, but The Athletic ships the ranking itself as static
HTML: one `div.fc-card` per player, carrying the rank, name, position, school,
and class level in classes/attributes even when the surrounding copy is hidden:

    <div class="paywall-hide fc-card ... fcf-position_player fcf-4-year_college fcf-ss"
         data-name="Roch Cholowsky">
      ... <div class="fc-rank-text">1</div> ...
          <div class="fc-stat-right">UCLA</div> ...

So a plain GET usually carries the whole board. fetch_paywalled() is the
fallback if The Athletic ever stops inlining the cards.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..base import SourceMeta, fetch_paywalled, get, ranking_row

SOURCE = SourceMeta(
    key="keith_law",
    name="The Athletic — Keith Law (Top 100)",
    url="https://www.nytimes.com/athletic/7271408/2026/05/14/mlb-draft-2026-top-100-prospects-roch-cholowsky/",
    access="paywall",
    weight=1.3,
)

# fcf-<token> classes carry the position; map the ones The Athletic uses.
_POS_CLASS = {
    "rhp": "RHP", "lhp": "LHP", "ss": "SS", "c": "C", "of": "OF",
    "1b": "1B", "2b": "2B", "3b": "3B", "util": "UTIL", "dh": "DH",
}
# A trailing "(City, State)" in the school string — grab the state.
_STATE = re.compile(r",\s*([A-Za-z][\w.]*)\s*\)\s*$")


def _parse(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows, seen = [], set()
    for card in soup.select("div.fc-card"):
        name = (card.get("data-name") or "").strip()
        rt = card.select_one(".fc-rank-text")
        if not name or rt is None:
            continue
        try:
            rank = int(rt.get_text(strip=True))
        except ValueError:
            continue
        if rank in seen:
            continue
        seen.add(rank)

        classes = card.get("class", [])
        position = next(
            (_POS_CLASS[c[4:]] for c in classes
             if c.startswith("fcf-") and c[4:] in _POS_CLASS),
            "",
        )
        class_level = (
            "HS" if "fcf-high_school" in classes
            else "College" if "fcf-4-year_college" in classes
            else ""
        )

        se = card.select_one(".fc-stat-right")
        school = se.get_text(strip=True) if se else ""
        sm = _STATE.search(school)

        rows.append(ranking_row(
            rank=rank,
            player=name,
            position=position,
            school=school,
            class_level=class_level,
            state=sm.group(1) if sm else "",
        ))
    return sorted(rows, key=lambda r: r["rank"])


def fetch() -> list[dict]:
    # 1) direct — The Athletic inlines the fc-card board in the static HTML.
    html = get(SOURCE.url, tag="keith_law_direct")
    if html:
        rows = _parse(html)
        if rows:
            return rows

    # 2) shared paywall chain (Wayback/archive.today) as a fallback.
    html = fetch_paywalled(SOURCE.url, tag="keith_law")
    if html:
        rows = _parse(html)
        if rows:
            return rows

    return []
