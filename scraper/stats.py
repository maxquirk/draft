"""Scrape 2025 college player stats for draft prospects.

Tries FanGraphs college stats leaderboard first (JSON API, no auth needed),
then falls back to the MLB Stats API draft prospects endpoint for any data available.
Matches players by name to consensus_2026.csv and writes player_stats_2026.csv.

Run standalone:  python -m scraper.stats
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .base import get_json
from .normalize import canon_name

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "app" / "data"

_FG_BAT_URL = "https://www.fangraphs.com/api/leaders/college-stats"
_FG_PIT_URL = "https://www.fangraphs.com/api/leaders/college-stats"

_COLS = [
    "player_id", "player", "stat_type",
    "avg", "obp", "slg", "ops", "hr", "rbi", "sb",
    "era", "whip", "k_9", "bb_9", "ip", "w", "sv",
]


def _safe(v, fmt=None) -> str:
    if v is None:
        return ""
    try:
        f = float(v)
        if fmt == "avg":
            return f"{f:.3f}"
        if fmt == "era":
            return f"{f:.2f}"
        return str(round(f, 2))
    except (TypeError, ValueError):
        return str(v)


def _fetch_fg_batters(season: int = 2025) -> list[dict]:
    data = get_json(_FG_BAT_URL, params={
        "pos": "all", "season": season, "stat": "bat",
        "lg": "all", "qual": "0", "type": "0",
    })
    if not data or not isinstance(data, (list, dict)):
        return []
    rows = data if isinstance(data, list) else data.get("data", [])
    out = []
    for r in rows:
        name = (r.get("PlayerName") or r.get("Name") or r.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "_canon": canon_name(name),
            "_name": name,
            "stat_type": "BATTER",
            "avg": _safe(r.get("AVG") or r.get("BA"), "avg"),
            "obp": _safe(r.get("OBP"), "avg"),
            "slg": _safe(r.get("SLG"), "avg"),
            "ops": _safe(r.get("OPS"), "avg"),
            "hr": _safe(r.get("HR")),
            "rbi": _safe(r.get("RBI")),
            "sb": _safe(r.get("SB")),
        })
    return out


def _fetch_fg_pitchers(season: int = 2025) -> list[dict]:
    data = get_json(_FG_PIT_URL, params={
        "pos": "all", "season": season, "stat": "pit",
        "lg": "all", "qual": "0", "type": "0",
    })
    if not data or not isinstance(data, (list, dict)):
        return []
    rows = data if isinstance(data, list) else data.get("data", [])
    out = []
    for r in rows:
        name = (r.get("PlayerName") or r.get("Name") or r.get("name") or "").strip()
        if not name:
            continue
        try:
            ip = float(r.get("IP") or 0)
            k9 = _safe(float(r.get("K/9") or r.get("K_9") or 0))
            bb9 = _safe(float(r.get("BB/9") or r.get("BB_9") or 0))
        except (TypeError, ValueError):
            k9, bb9, ip = "", "", ""
        out.append({
            "_canon": canon_name(name),
            "_name": name,
            "stat_type": "PITCHER",
            "era": _safe(r.get("ERA"), "era"),
            "whip": _safe(r.get("WHIP")),
            "k_9": k9,
            "bb_9": bb9,
            "ip": _safe(ip),
            "w": _safe(r.get("W")),
            "sv": _safe(r.get("SV")),
        })
    return out


def build() -> None:
    """Fetch stats and match to consensus players, writing player_stats_2026.csv."""
    consensus_fp = DATA / "consensus_2026.csv"
    if not consensus_fp.exists():
        print("   ! consensus_2026.csv not found — run scraper.run first")
        return

    # Load college players only
    prospects: list[dict] = []
    with open(consensus_fp, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if str(row.get("class_level", "")).strip().lower() in ("college", "juco"):
                prospects.append({
                    "player_id": row.get("player_id", ""),
                    "player": row.get("player", ""),
                    "_canon": canon_name(row.get("player", "")),
                    "position": row.get("position", "").upper(),
                })

    print(f"   {len(prospects)} college prospects to match stats for")

    batters = _fetch_fg_batters()
    pitchers = _fetch_fg_pitchers()
    print(f"   FanGraphs returned {len(batters)} batter rows, {len(pitchers)} pitcher rows")

    bat_lookup = {r["_canon"]: r for r in batters}
    pit_lookup = {r["_canon"]: r for r in pitchers}

    matched = 0
    out_rows: list[dict] = []
    for p in prospects:
        ck = p["_canon"]
        pos = p["position"]
        is_pitcher = any(x in pos for x in ("RHP", "LHP", "P"))

        stats_row = pit_lookup.get(ck) if is_pitcher else bat_lookup.get(ck)
        if not stats_row:
            stats_row = bat_lookup.get(ck) or pit_lookup.get(ck)

        if not stats_row:
            continue

        matched += 1
        out_rows.append({
            "player_id": p["player_id"],
            "player": p["player"],
            "stat_type": stats_row.get("stat_type", "BATTER"),
            "avg": stats_row.get("avg", ""),
            "obp": stats_row.get("obp", ""),
            "slg": stats_row.get("slg", ""),
            "ops": stats_row.get("ops", ""),
            "hr": stats_row.get("hr", ""),
            "rbi": stats_row.get("rbi", ""),
            "sb": stats_row.get("sb", ""),
            "era": stats_row.get("era", ""),
            "whip": stats_row.get("whip", ""),
            "k_9": stats_row.get("k_9", ""),
            "bb_9": stats_row.get("bb_9", ""),
            "ip": stats_row.get("ip", ""),
            "w": stats_row.get("w", ""),
            "sv": stats_row.get("sv", ""),
        })

    print(f"   Matched stats for {matched}/{len(prospects)} college prospects")

    out_fp = DATA / "player_stats_2026.csv"
    with open(out_fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(f"   -> wrote app/data/player_stats_2026.csv  ({len(out_rows)} rows)")


if __name__ == "__main__":
    build()
