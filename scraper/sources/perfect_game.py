"""Perfect Game 2026 Draft Board — Top 300.

The article body is a single HTML table with columns:
    Rk. | Name | Level | Pos. | B-T | School | Hometown | State | Commitment
"Level" is "C" (college) or "H" (high school); "Commitment" is the HS player's
college pledge, which we fold into notes.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ..base import SourceMeta, get, ranking_row

SOURCE = SourceMeta(
    key="perfect_game",
    name="Perfect Game 2026 Draft Top 300",
    url="https://www.perfectgame.org/Articles/View.aspx?article=24219",
    access="free",
)

_LEVEL = {"C": "College", "H": "HS", "J": "JUCO"}


def fetch() -> list[dict]:
    html = get(SOURCE.url, tag="pg")
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 8:
            continue  # header row (uses <th>) or malformed
        rk, name, level, pos, bt, school, hometown, state = cells[:8]
        commit = cells[8] if len(cells) > 8 else ""
        if not rk.isdigit() or not name:
            continue
        notes = []
        if bt:
            notes.append(f"B-T {bt}")
        if hometown:
            notes.append(hometown)
        if commit:
            notes.append(f"committed {commit}")
        rows.append(ranking_row(
            rank=rk,
            player=name,
            position=pos,
            school=school,
            class_level=_LEVEL.get(level, ""),
            state=state,
            notes="; ".join(notes),
            source=SOURCE.key,
        ))
    return rows
