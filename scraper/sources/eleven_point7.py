"""11Point7 2026 Prospect Big Board (college-focused).

A Webflow CMS collection. Each player is a `div.collection-item-20` with
semantic sub-fields: prospect-rank, prospect-name-cont, prospect-position,
school (div-block-363), college class (div-block-532), and hometown
(div-block-362, "City, ST"). The board is entirely college players.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ..base import SourceMeta, get, ranking_row

SOURCE = SourceMeta(
    key="eleven_point7",
    name="11Point7 2026 Prospect Big Board",
    url="https://www.11point7.com/mlb-draft/2026-prospect-big-board",
    access="free",
)


def _field(item, cls: str) -> str:
    e = item.select_one("div." + cls)
    return e.get_text(" ", strip=True) if e else ""


def fetch() -> list[dict]:
    html = get(SOURCE.url, tag="11p7")
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    rows: list[dict] = []
    for item in soup.select("div.collection-item-20"):
        rk = _field(item, "prospect-rank")
        name = _field(item, "prospect-name-cont")
        if not rk.isdigit() or not name:
            continue
        loc = _field(item, "div-block-362")  # "City, ST"
        state = loc.rsplit(",", 1)[-1].strip() if "," in loc else ""
        cls = _field(item, "div-block-532").replace("Age:", "").strip()  # e.g. "21.0 JR"
        rows.append(ranking_row(
            rank=rk,
            player=name,
            position=_field(item, "prospect-position"),
            school=_field(item, "div-block-363"),
            class_level="College",
            state=state,
            notes=(f"{loc}; {cls}".strip("; ") if loc or cls else ""),
            source=SOURCE.key,
        ))
    return rows
