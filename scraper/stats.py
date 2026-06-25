"""Scrape 2025 college player stats for draft prospects from Baseball Reference.

Uses BR search to find each college player's register page, then extracts
their most recent season stats. HS players are skipped (no college stats).

Writes app/data/player_stats_2026.csv.
Run standalone:  python -m scraper.stats
"""
from __future__ import annotations

import csv
import re
import time
from pathlib import Path

from .base import get
from .normalize import canon_name

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "app" / "data"

_BR_SEARCH = "https://www.baseball-reference.com/search/search.fcgi"
_COLS = [
    "player_id", "player", "stat_type",
    "avg", "obp", "slg", "ops", "hr", "rbi", "sb",
    "era", "whip", "k_9", "bb_9", "ip", "w", "sv",
]


def _safe_float(val: str) -> str:
    try:
        return str(round(float(val), 3))
    except (TypeError, ValueError):
        return ""


def _fetch_br_player_url(name: str) -> str | None:
    """Search BR for the player and return the first matching register URL."""
    search_url = f"{_BR_SEARCH}?search={name.replace(' ', '+')}"
    html = get(search_url, tag=f"br_search_{canon_name(name)[:20]}", cache=True)
    if not html:
        return None

    # Direct match: BR redirected to a player page
    if "/players/" in html and "register" in html.lower():
        reg = re.search(r'href="(/register/player\.fcgi[^"]+)"', html)
        if reg:
            return "https://www.baseball-reference.com" + reg.group(1)

    # Search result page: find the register link
    links = re.findall(r'href="(/register/player\.fcgi[^"]+)"', html)
    if links:
        return "https://www.baseball-reference.com" + links[0]

    return None


def _parse_stats_from_register(url: str, season: int = 2025) -> dict | None:
    """Fetch the BR register page and extract the specified season's batting or pitching stats."""
    html = get(url, tag=f"br_reg_{hash(url) & 0xFFFF}", cache=True)
    if not html:
        return None

    # Determine stat type — does this page have a batting or pitching table?
    has_bat = bool(re.search(r'<table[^>]+id="(batting_standard|bat_stats)"', html))
    has_pit = bool(re.search(r'<table[^>]+id="(pitching_standard|pit_stats)"', html))

    def _extract_row(table_id_pattern: str) -> dict:
        table_m = re.search(rf'<table[^>]+id="{table_id_pattern}"[^>]*>(.*?)</table>', html, re.S | re.I)
        if not table_m:
            return {}
        tbody = re.search(r'<tbody>(.*?)</tbody>', table_m.group(1), re.S)
        if not tbody:
            return {}
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody.group(1), re.S)
        # Find most recent season matching `season`
        for row in reversed(rows):
            year_m = re.search(r'data-stat="year_ID"[^>]*>([^<]+)', row)
            if not year_m:
                continue
            yr = year_m.group(1).strip()
            if str(season) in yr or str(season - 1) in yr:
                cells = re.findall(r'data-stat="([^"]+)"[^>]*>([^<]*)', row)
                return {k: re.sub(r"<[^>]+>", "", v).strip() for k, v in cells}
        # Fall back to last row with data
        for row in reversed(rows):
            if "<td" in row:
                cells = re.findall(r'data-stat="([^"]+)"[^>]*>([^<]*)', row)
                d = {k: re.sub(r"<[^>]+>", "", v).strip() for k, v in cells}
                if any(d.get(k) for k in ("batting_avg", "onbase_plus_slugging", "earned_run_avg")):
                    return d
        return {}

    if has_bat:
        d = _extract_row(r"batting_standard|bat_stats|standard_batting")
        if d:
            return {
                "stat_type": "BATTER",
                "avg": _safe_float(d.get("batting_avg", "")),
                "obp": _safe_float(d.get("onbase_perc", d.get("onbase_pct", ""))),
                "slg": _safe_float(d.get("slugging_perc", d.get("slugging_pct", ""))),
                "ops": _safe_float(d.get("onbase_plus_slugging", "")),
                "hr": d.get("HR", ""),
                "rbi": d.get("RBI", ""),
                "sb": d.get("SB", ""),
            }
    if has_pit:
        d = _extract_row(r"pitching_standard|pit_stats|standard_pitching")
        if d:
            ip = d.get("IP", "")
            so = float(d.get("SO", 0) or 0)
            bb = float(d.get("BB", 0) or 0)
            ip_f = float(ip) if ip else 0.0
            k9 = f"{9 * so / ip_f:.2f}" if ip_f > 0 else ""
            bb9 = f"{9 * bb / ip_f:.2f}" if ip_f > 0 else ""
            return {
                "stat_type": "PITCHER",
                "era": _safe_float(d.get("earned_run_avg", "")),
                "whip": _safe_float(d.get("whip", "")),
                "k_9": k9,
                "bb_9": bb9,
                "ip": ip,
                "w": d.get("W", ""),
                "sv": d.get("SV", ""),
            }
    return None


def build() -> None:
    """Fetch stats for all college prospects and write player_stats_2026.csv."""
    consensus_fp = DATA / "consensus_2026.csv"
    if not consensus_fp.exists():
        print("   ! consensus_2026.csv not found")
        return

    prospects: list[dict] = []
    with open(consensus_fp, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if str(row.get("class_level", "")).strip().lower() in ("college", "juco"):
                prospects.append({
                    "player_id": row.get("player_id", ""),
                    "player": row.get("player", ""),
                    "position": row.get("position", "").upper(),
                })

    print(f"   Fetching BR stats for {len(prospects)} college prospects ...")

    out_rows: list[dict] = []
    matched = 0

    for p in prospects:
        player_url = _fetch_br_player_url(p["player"])
        if not player_url:
            continue

        stats = _parse_stats_from_register(player_url)
        if not stats:
            continue

        matched += 1
        empty = {"avg": "", "obp": "", "slg": "", "ops": "", "hr": "", "rbi": "", "sb": "",
                 "era": "", "whip": "", "k_9": "", "bb_9": "", "ip": "", "w": "", "sv": ""}
        out_rows.append({
            "player_id": p["player_id"],
            "player": p["player"],
            **{**empty, **stats},
        })
        time.sleep(3.0)  # BR rate-limits aggressively — 3s between requests

    print(f"   Matched stats for {matched}/{len(prospects)} college prospects")

    out_fp = DATA / "player_stats_2026.csv"
    with open(out_fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(f"   -> wrote app/data/player_stats_2026.csv  ({len(out_rows)} rows)")


if __name__ == "__main__":
    build()
