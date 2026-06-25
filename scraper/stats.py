"""Scrape 2026 college stats for draft prospects from The Baseball Cube.

Fetches per-school team stats pages at stats_college/2026~{tbc_id}/ and matches
players by name within the correct roster. School→TBC ID mapping is hardcoded
from TBC's school list pages (/content/schools/, /content/schools/juco/, etc.).

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

_TBC_TEAM_STATS = "https://www.thebaseballcube.com/content/stats_college/2026~{}/"

# School name (as it appears in consensus_2026.csv) → TBC college_history ID
# IDs sourced from https://www.thebaseballcube.com/content/schools/ (D1/D2/JUCO/NAIA lists)
_SCHOOL_ID_MAP: dict[str, str] = {
    "Alabama":                      "20048",
    "Arizona":                      "20026",
    "Arizona State":                "20021",
    "Arkansas":                     "20344",
    "Auburn":                       "20071",
    "Blinn (Texas) JC":             "20349",
    "Central Florida":              "20443",
    "Cincinnati":                   "20357",
    "Clemson":                      "20089",
    "Coastal Carolina":             "20319",
    "Connecticut":                  "20223",
    "Copiah-Lincoln (MS) JC":       "21003",
    "East Carolina":                "20384",
    "Enterprise (Ala.) JC":         "20724",
    "Everett (Wash.) JC":           "21020",
    "Florida":                      "20177",
    "Florida Gulf Coast":           "21988",
    "Florida State":                "20022",
    "George Washington":            "20070",
    "Georgia":                      "20350",
    "Georgia Tech":                 "20124",
    "Heartland (Ill.) JC":          "22406",
    "Houston":                      "20254",
    "Indiana State":                "20256",
    "Jacksonville State":           "20131",
    "Kansas":                       "20454",
    "Kansas State":                 "20398",
    "Kentucky":                     "20017",
    "LSU":                          "20004",
    "Liberty":                      "20403",
    "Louisville":                   "20457",
    "McLennan JC (TX)":             "20068",
    "Miami":                        "20182",
    "Minnesota":                    "20011",
    "Mississippi":                  "20085",
    "Mississippi State":            "20147",
    "Missouri":                     "20458",
    "Missouri State":               "20219",
    "Monterey Peninsula (Calif.) JC": "21185",
    "Nebraska":                     "20066",
    "North Carolina":               "20006",
    "North Carolina State":         "20235",
    "Notre Dame":                   "20151",
    "Oklahoma":                     "20214",
    "Oklahoma State":               "20093",
    "Ole Miss":                     "20085",
    "Oregon":                       "20465",
    "Oregon State":                 "20272",
    "Pittsburgh":                   "20358",
    "Rutgers":                      "20097",
    "Sacramento City (Calif.) JC":  "20243",
    "Sam Houston State":            "20258",
    "South Carolina":               "20091",
    "TCU":                          "20433",
    "Tennessee":                    "20015",
    "Texas":                        "20193",
    "Texas A&M":                    "20023",
    "Texas Tech":                   "20169",
    "UC Irvine":                    "20029",
    "UC San Diego":                 "20644",
    "UC Santa Barbara":             "20304",
    "UCLA":                         "20054",
    "USC":                          "20064",
    "Vanderbilt":                   "20231",
    "Virginia":                     "20194",
    "Virginia Tech":                "20293",
    "Wake Forest":                  "20094",
    "West Virginia":                "20195",
}

_COLS = [
    "player_id", "player", "stat_type",
    "avg", "obp", "slg", "ops", "hr", "rbi", "sb",
    "era", "whip", "k_9", "bb_9", "ip", "w", "sv",
]

# Cache: tbc_id → {canon_name: stats_dict}
_team_cache: dict[str, dict[str, dict]] = {}


def _load_team(tbc_id: str) -> dict[str, dict]:
    if tbc_id in _team_cache:
        return _team_cache[tbc_id]

    html = get(_TBC_TEAM_STATS.format(tbc_id), tag=f"tbc_team_{tbc_id}_2026", cache=True)
    if not html:
        _team_cache[tbc_id] = {}
        return {}

    result: dict[str, dict] = {}
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.S | re.I)

    for t in tables:
        header = re.search(r"<tr[^>]*class=['\"]header-row[^>]*>(.*?)</tr>", t, re.S)
        if not header:
            continue
        cols = [c.strip().lower() for c in re.findall(r"<td[^>]*>([^<]+)</td>", header.group(1))]
        is_bat = "avg" in cols and "ab" in cols
        is_pit = "era" in cols and "ip" in cols
        if not is_bat and not is_pit:
            continue

        for row in re.findall(r"<tr[^>]*class=['\"]data-row[^>]*>(.*?)</tr>", t, re.S):
            cells = re.findall(r"<td[^>]*>(?:<a[^>]*>)?([^<]*)(?:</a>)?</td>", row)
            d = dict(zip(cols, cells))
            raw_name = d.get("player", "").strip()
            if not raw_name or raw_name == "&nbsp;":
                continue
            key = canon_name(raw_name)
            if key in result:
                continue
            if is_bat:
                result[key] = {
                    "stat_type": "BATTER",
                    "avg": d.get("avg", ""),
                    "obp": d.get("obp", ""),
                    "slg": d.get("slg", ""),
                    "ops": d.get("ops", ""),
                    "hr":  d.get("hr", ""),
                    "rbi": d.get("rbi", ""),
                    "sb":  d.get("sb", ""),
                }
            else:
                result[key] = {
                    "stat_type": "PITCHER",
                    "era":  d.get("era", ""),
                    "whip": d.get("whip", ""),
                    "k_9":  d.get("so9", ""),
                    "bb_9": d.get("bb9", ""),
                    "ip":   d.get("ip", ""),
                    "w":    d.get("w", ""),
                    "sv":   d.get("sv", ""),
                }

    _team_cache[tbc_id] = result
    return result


def _find_player(player: str, roster: dict[str, dict]) -> dict | None:
    target = canon_name(player)
    if target in roster:
        return roster[target]
    # Fuzzy fallback for nicknames / initials
    best_key, best_score = None, 0
    for key in roster:
        score = fuzz.token_sort_ratio(target, key)
        if score > best_score:
            best_score, best_key = score, key
    return roster[best_key] if best_score >= 80 else None


def build() -> None:
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
                    "player":    row.get("player", ""),
                    "school":    row.get("school", "").strip(),
                })

    print(f"   Fetching TBC 2026 team stats for {len(prospects)} college/JUCO prospects ...")

    # Pre-fetch unique school pages
    unique_schools = sorted({p["school"] for p in prospects if p["school"] in _SCHOOL_ID_MAP})
    print(f"   Loading {len(unique_schools)}/{len({p['school'] for p in prospects})} school rosters ...")
    for school in unique_schools:
        _load_team(_SCHOOL_ID_MAP[school])

    out_rows: list[dict] = []
    matched, no_map, no_player = 0, [], []
    empty = {k: "" for k in _COLS if k not in ("player_id", "player", "stat_type")}

    for p in prospects:
        tbc_id = _SCHOOL_ID_MAP.get(p["school"])
        if not tbc_id:
            no_map.append(f"{p['player']} ({p['school']})")
            continue
        roster = _team_cache.get(tbc_id, {})
        stats = _find_player(p["player"], roster)
        if not stats:
            no_player.append(f"{p['player']} ({p['school']})")
            continue
        matched += 1
        out_rows.append({"player_id": p["player_id"], "player": p["player"], **{**empty, **stats}})

    print(f"   Matched 2026 stats for {matched}/{len(prospects)} college prospects")
    if no_map:
        print(f"   No school mapping ({len(no_map)}): {', '.join(no_map)}")
    if no_player:
        print(f"   Not on 2026 roster ({len(no_player)}): {', '.join(no_player)}")

    out_fp = DATA / "player_stats_2026.csv"
    with open(out_fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(f"   -> wrote app/data/player_stats_2026.csv  ({len(out_rows)} rows)")


if __name__ == "__main__":
    build()
