"""Baseball America — 2026 top MLB draft prospects (top 500).

The on-page ranking table is rendered client-side and gated behind BA's
"piano" paywall, so the static article HTML only carries a 5-name prose
preview. The same WordPress install, however, exposes the full board as
structured JSON through its public REST endpoint:

    /wp-json/bba/v1/ranking-types/<rankingPostId>

We read the post id off the article (the body element carries a
`postid-<n>` class) and pull the board from that endpoint. The fetch_paywalled
chain is kept as a fallback in case the JSON route ever closes.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..base import SourceMeta, fetch_paywalled, get, get_json, ranking_row

SOURCE = SourceMeta(
    key="baseball_america",
    name="Baseball America — 2026 Top Draft Prospects (Top 500)",
    url="https://www.baseballamerica.com/rankings/2026-top-mlb-draft-prospects/",
    access="paywall",
    weight=1.3,
)

_API = "https://www.baseballamerica.com/wp-json/bba/v1/ranking-types/{post_id}"
_SCHOOL = re.compile(r"<strong>\s*School:\s*</strong>\s*([^<]+)", re.I)
_COMMIT = re.compile(r"<strong>\s*Committed/Drafted:\s*</strong>\s*([^<]+)", re.I)


def _post_id(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select('[class*="postid-"]'):
        for cls in el.get("class", []):
            m = re.fullmatch(r"postid-(\d+)", cls)
            if m:
                return m.group(1)
    m = re.search(r"postid-(\d+)", html)
    return m.group(1) if m else None


def _rows_from_api(post_id: str) -> list[dict]:
    data = get_json(_API.format(post_id=post_id))
    rankings = (data or {}).get("rankings") or []
    rows = []
    for e in rankings:
        rank = e.get("rank")
        name = (e.get("playerDisplayName") or "").strip()
        if not rank or not name:
            continue

        body = (e.get("report") or {}).get("body") or ""
        sm = _SCHOOL.search(body)
        # The report school text ("UCLA" / "Gulliver Prep HS, Miami") is the
        # current/draft-relevant school; the player.schools array is the raw
        # history and often shows the HS for a college junior.
        school = sm.group(1).strip().rstrip(".") if sm else ""

        cm = _COMMIT.search(body)
        commit = cm.group(1).strip().rstrip(".") if cm else ""
        notes = []
        if commit and commit.lower() not in ("never drafted",):
            notes.append(f"commit/drafted: {commit}")
        if e.get("playerAge"):
            notes.append(f"age {e['playerAge']}")

        pos = (e.get("primaryPositionCode") or "").strip()
        sec = (e.get("secondaryPositionCode") or "").strip()
        if sec:
            pos = f"{pos}/{sec}"

        rows.append(ranking_row(
            rank=rank,
            player=name,
            position=pos,
            school=school,
            notes="; ".join(notes),
        ))
    return sorted(rows, key=lambda r: r["rank"])


def fetch() -> list[dict]:
    html = get(SOURCE.url, tag="baseball_america_direct")
    if html:
        post_id = _post_id(html)
        if post_id:
            rows = _rows_from_api(post_id)
            if rows:
                return rows

    # Fallback: the paywall chain may surface an archived copy with the post id.
    archived = fetch_paywalled(SOURCE.url, tag="baseball_america")
    if archived:
        post_id = _post_id(archived)
        if post_id:
            rows = _rows_from_api(post_id)
            if rows:
                return rows

    return []
