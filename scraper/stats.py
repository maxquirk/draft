"""Scrape 2025 college player stats for draft prospects from The Baseball Cube.

Uses TBC's AJAX search to find player IDs, then fetches per-player pages for
NCAA stats. HS players are skipped (no college stats). JUCO players included.

Writes app/data/player_stats_2026.csv.
Run standalone:  python -m scraper.stats
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from rapidfuzz import fuzz

from .base import get
from .normalize import canon_name

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "app" / "data"

_TBC_SEARCH = "https://www.thebaseballcube.com/code_2026/ajax/search_top.asp"
_TBC_PLAYER = "https://www.thebaseballcube.com/content/player/{}/"

_NCAA_LEVELS = {"NCAA-1", "NCAA-2", "NCAA-3", "NAIA", "NJCAA", "JUCO", "COLL", "CCBC"}

_COLS = [
    "player_id", "player", "stat_type",
    "avg", "obp", "slg", "ops", "hr", "rbi", "sb",
    "era", "whip", "k_9", "bb_9", "ip", "w", "sv",
]


def _tbc_id_for(name: str) -> str | None:
    """Search TBC by last name, return the TBC player ID for the best match."""
    parts = name.strip().split()
    if len(parts) < 2:
        return None
    last = parts[-1]
    html = get(_TBC_SEARCH, params={"Q": last}, tag=f"tbc_search_{canon_name(last)[:20]}", cache=True)
    if not html:
        return None

    # Parse rows: id, display_name from onclick and <a> text
    entries = re.findall(
        r"goto_url\(['\"][^'\"]+/player/(\d+)/['\"].*?<a[^>]+>([^<]+)</a>",
        html, re.S
    )
    if not entries:
        return None

    canon = canon_name(name)
    best_id, best_score = None, 0
    for tbc_id, tbc_name in entries:
        score = fuzz.token_sort_ratio(canon, canon_name(tbc_name))
        if score > best_score:
            best_score, best_id = score, tbc_id

    return best_id if best_score >= 80 else None


def _parse_player_page(tbc_id: str) -> dict | None:
    """Fetch TBC player page and return 2025 NCAA batting or pitching stats."""
    url = _TBC_PLAYER.format(tbc_id)
    html = get(url, tag=f"tbc_player_{tbc_id}", cache=True)
    if not html:
        return None

    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.S | re.I)
    batting, pitching = None, None

    for t in tables:
        header = re.search(r"<tr[^>]*class=['\"]header-row[^>]*>(.*?)</tr>", t, re.S)
        if not header:
            continue
        cols = re.findall(r"<td[^>]*>([^<]+)</td>", header.group(1))
        cols = [c.strip().lower() for c in cols]

        is_bat = "avg" in cols and "ab" in cols
        is_pit = "era" in cols and "ip" in cols

        if not is_bat and not is_pit:
            continue

        data_rows = re.findall(r"<tr[^>]*class=['\"]data-row[^>]*>(.*?)</tr>", t, re.S)
        # Collect all rows, prefer 2025, fallback to most recent college season
        candidate_rows: list[dict] = []
        for row in data_rows:
            cells = re.findall(r"<td[^>]*>(?:<a[^>]*>)?([^<]*)(?:</a>)?</td>", row)
            d = dict(zip(cols, cells))
            level = d.get("level", "").strip()
            if not any(lvl in level for lvl in _NCAA_LEVELS):
                continue
            candidate_rows.append(d)

        if not candidate_rows:
            continue

        # Prefer 2025, then take last in list
        chosen = next((d for d in reversed(candidate_rows) if "2025" in d.get("year", "")), None)
        if chosen is None:
            chosen = candidate_rows[-1]

        if is_bat and batting is None:
            batting = chosen
        elif is_pit and pitching is None:
            pitching = chosen

    if batting:
        return {
            "stat_type": "BATTER",
            "avg": batting.get("avg", ""),
            "obp": batting.get("obp", ""),
            "slg": batting.get("slg", ""),
            "ops": batting.get("ops", ""),
            "hr": batting.get("hr", ""),
            "rbi": batting.get("rbi", ""),
            "sb": batting.get("sb", ""),
        }
    if pitching:
        return {
            "stat_type": "PITCHER",
            "era": pitching.get("era", ""),
            "whip": pitching.get("whip", ""),
            "k_9": pitching.get("so9", ""),
            "bb_9": pitching.get("bb9", ""),
            "ip": pitching.get("ip", ""),
            "w": pitching.get("w", ""),
            "sv": pitching.get("sv", ""),
        }
    return None


def build() -> None:
    """Fetch stats for all college/JUCO prospects and write player_stats_2026.csv."""
    consensus_fp = DATA / "consensus_2026.csv"
    if not consensus_fp.exists():
        print("   ! consensus_2026.csv not found")
        return

    prospects: list[dict] = []
    with open(consensus_fp, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lvl = str(row.get("class_level", "")).strip().lower()
            if lvl in ("college", "juco"):
                prospects.append({
                    "player_id": row.get("player_id", ""),
                    "player": row.get("player", ""),
                })

    print(f"   Fetching TBC stats for {len(prospects)} college/JUCO prospects ...")

    out_rows: list[dict] = []
    matched = 0
    empty = {k: "" for k in _COLS if k not in ("player_id", "player", "stat_type")}

    for p in prospects:
        name = p["player"]
        tbc_id = _tbc_id_for(name)
        if not tbc_id:
            continue
        stats = _parse_player_page(tbc_id)
        if not stats:
            continue
        matched += 1
        out_rows.append({"player_id": p["player_id"], "player": name, **{**empty, **stats}})

    print(f"   Matched stats for {matched}/{len(prospects)} college prospects")

    out_fp = DATA / "player_stats_2026.csv"
    with open(out_fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(f"   -> wrote app/data/player_stats_2026.csv  ({len(out_rows)} rows)")


if __name__ == "__main__":
    build()
