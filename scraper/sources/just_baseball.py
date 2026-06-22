"""Just Baseball 2026 MLB Draft rankings.

Just Baseball publishes its 2026 board as TWO separate top-100 lists rather
than one combined board:
    - "Top 100 College Prospects"  (overall best-available; #1 Roch Cholowsky)
    - "Top 100 Prep Prospects"     (high-school only; #1 Grady Emerson)

We return the College list as the source's board because it is the
apples-to-apples "best player available" ranking comparable to the other
sources (Perfect Game / 11Point7 both lead with Cholowsky). The Prep list is a
separate HS-only product with its own rank 1 — folding it in would either
duplicate rank-1 under one source or fabricate a cross-list ordering, so it is
intentionally not merged here. `fetch_prep()` exposes it if the orchestrator
ever wants it as a distinct source.

Each list is a WordPress post whose body is a sequence of headings
("N. Player Name - POS") each followed by a metadata <p>:
    HT/WT: ... | Bat/Throw: ... | School: ... | Hometown/Commitment: ... | ...
We pull content through the WP REST API (the public HTML page is JS-gated).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..base import SourceMeta, get_json, ranking_row

SOURCE = SourceMeta(
    key="just_baseball",
    name="Just Baseball",
    url="https://www.justbaseball.com/mlb-draft/mlb-draft-top-college-prospects/",
    access="free",
)

_API = "https://www.justbaseball.com/wp-json/wp/v2/posts"
_HEAD_RE = re.compile(r"^\s*(\d+)\.\s*(.+)$")
_STATE_RE = re.compile(r"\(([A-Z]{2})\)")


def _meta(text: str) -> dict:
    out = {}
    for part in text.split("|"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def _parse_post(slug: str, class_level: str) -> list[dict]:
    res = get_json(_API, params={"slug": slug})
    if not res:
        return []
    soup = BeautifulSoup(res[0]["content"]["rendered"], "lxml")
    rows: list[dict] = []
    for h in soup.find_all(["h2", "h3", "h4"]):
        m = _HEAD_RE.match(h.get_text(" ", strip=True))
        if not m:
            continue
        rank = m.group(1)
        # heading body is "Player Name - POS" (en-dash or hyphen)
        body = re.split(r"\s[–—-]\s", m.group(2), maxsplit=1)
        player = body[0].strip()
        position = body[1].strip() if len(body) > 1 else ""
        if not player:
            continue

        meta_p = h.find_next("p")
        meta = _meta(meta_p.get_text(" ", strip=True)) if meta_p else {}
        school = meta.get("school", "")
        # State: prep schools carry it as "(TX)"; college entries carry the
        # player's hometown as "City, ST".
        sm = _STATE_RE.search(school) or re.search(r",\s*([A-Z]{2})\b", meta.get("hometown", ""))
        state = sm.group(1) if sm else ""
        school_clean = _STATE_RE.sub("", school).strip()
        note_bits = []
        for k in ("hometown", "commitment", "bat/throw"):
            if meta.get(k):
                note_bits.append(f"{k}: {meta[k]}")
        rows.append(ranking_row(
            rank=rank,
            player=player,
            position=position,
            school=school_clean,
            class_level=class_level,
            state=state,
            notes="; ".join(note_bits),
            source=SOURCE.key,
        ))
    return rows


def fetch() -> list[dict]:
    """Both Just Baseball lists combined into one board (college + prep).

    Each list is its own 1..100 ranking, so a college player and a prep player can
    share a rank number — that's fine: they are different players, each keeps their
    own list rank. This gives Just Baseball coverage of HS prospects (Grady Emerson,
    Jacob Lombard, ...) who are absent from the college list.
    """
    return _parse_post("mlb-draft-top-college-prospects", "College") + fetch_prep()


def fetch_prep() -> list[dict]:
    """Just Baseball's separate HS-only top-100 (not merged into the main board)."""
    return _parse_post("2026-mlb-draft-top-prep-prospects", "HS")
