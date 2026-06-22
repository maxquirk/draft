"""Team draft-history pipeline for the 2026 MLB Draft Hub.

Scrapes Baseball-Reference's per-year June Amateur Draft pages (2018-2025) and the
2025 final standings, then writes three small static JSON files into app/data/ that
the shinylive app reads offline:

    team_draft_history.json   every 1st-round pick across the scraped years
    team_tendencies.json      per-team summary (college vs HS, pitcher vs hitter, ...)
    draft_order_2026.json     projected 2026 1st-round order (2025 standings inverse)

Run `python -m scraper.team_history` (or call build()) to (re)generate the files.
Picks/standings are scraped from real pages — nothing here is fabricated. Years that
fail to fetch/parse are skipped and reported, never invented.
"""
from __future__ import annotations

import io
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from .base import ROOT, get

# app/data/ lives one level up from scraper/ (ROOT == scraper/).
DATA_DIR = ROOT.parent / "app" / "data"

DRAFT_URL = "https://www.baseball-reference.com/draft/"
STANDINGS_URL = "https://www.baseball-reference.com/leagues/majors/{year}-standings.shtml"

YEARS = list(range(2018, 2026))  # 2018..2025 inclusive (current front-office era)
ROUNDS = [1]  # 1st round is the priority; widen here if more depth is ever needed.

# Baseball-Reference prints team nicknames (no city) in the draft tables, and uses the
# franchise's name *as of that draft year* — so older years carry retired names. Map
# every nickname (current + historical) to the current full club name.
TEAM_FULL = {
    "Diamondbacks": "Arizona Diamondbacks",
    "Braves": "Atlanta Braves",
    "Orioles": "Baltimore Orioles",
    "Red Sox": "Boston Red Sox",
    "Cubs": "Chicago Cubs",
    "White Sox": "Chicago White Sox",
    "Reds": "Cincinnati Reds",
    "Guardians": "Cleveland Guardians",
    "Indians": "Cleveland Guardians",      # renamed after 2021
    "Rockies": "Colorado Rockies",
    "Tigers": "Detroit Tigers",
    "Astros": "Houston Astros",
    "Royals": "Kansas City Royals",
    "Angels": "Los Angeles Angels",
    "Dodgers": "Los Angeles Dodgers",
    "Marlins": "Miami Marlins",
    "Brewers": "Milwaukee Brewers",
    "Twins": "Minnesota Twins",
    "Mets": "New York Mets",
    "Yankees": "New York Yankees",
    "Athletics": "Athletics",              # franchise dropped its city ahead of 2025
    "Phillies": "Philadelphia Phillies",
    "Pirates": "Pittsburgh Pirates",
    "Padres": "San Diego Padres",
    "Giants": "San Francisco Giants",
    "Mariners": "Seattle Mariners",
    "Cardinals": "St. Louis Cardinals",
    "Rays": "Tampa Bay Rays",
    "Rangers": "Texas Rangers",
    "Blue Jays": "Toronto Blue Jays",
    "Nationals": "Washington Nationals",
}

# The 30 current franchises (full names) — the universe team_tendencies.json must cover.
ALL_TEAMS = sorted(set(TEAM_FULL.values()))

_PAREN = re.compile(r"\s*\(.*?\)\s*$")  # strips trailing " (minors)" / " (FA)" etc.


def _cell(v) -> str:
    """A DataFrame cell as a clean string; pandas NaN (a float) becomes ''."""
    return "" if v is None or pd.isna(v) else str(v).strip()


def _team_full(nickname) -> str:
    nick = _cell(nickname)
    return TEAM_FULL.get(nick, nick)


def _clean_name(name) -> str:
    return _PAREN.sub("", _cell(name)).strip()


def _level(bref_type) -> str:
    """Map BR's Type column (4Yr / HS / JC) to College / HS / JUCO."""
    t = _cell(bref_type).lower()
    if t == "hs":
        return "HS"
    if t in ("jc", "juco"):
        return "JUCO"
    if t in ("4yr", "4 yr", "col", "college"):
        return "College"
    return ""


def _school(drafted_out_of) -> str:
    """BR's 'Drafted Out of' is e.g. 'Oregon State University (Corvallis, OR)' —
    keep the institution, drop the trailing '(City, ST)'."""
    return _PAREN.sub("", _cell(drafted_out_of)).strip()


# Position buckets for the per-team breakdown. BR's draft table has a single "P" for
# pitchers (no L/R handedness), so we bucket pitchers as "P" rather than fabricate
# RHP/LHP. Hitters split into C / IF / OF; two-way (TWP) counts as a hitter+pitcher edge
# case we file under "P" (its draft value is overwhelmingly the arm).
_PITCHER_POS = {"P", "RHP", "LHP", "SP", "RP", "PITCHER"}
_CATCHER_POS = {"C"}
_INFIELD_POS = {"1B", "2B", "3B", "SS", "IF", "INF"}
_OUTFIELD_POS = {"OF", "CF", "RF", "LF", "OUTFIELD"}


def _pos_bucket(pos) -> str:
    p = _cell(pos).upper()
    if p in _PITCHER_POS or p == "TWP":
        return "P"
    if p in _CATCHER_POS:
        return "C"
    if p in _INFIELD_POS:
        return "IF"
    if p in _OUTFIELD_POS:
        return "OF"
    return "OTHER"


def _scrape_year(year: int, rnd: int) -> list[dict]:
    """Return pick dicts for one draft year+round, or [] if the page can't be parsed."""
    params = {
        "year_ID": year,
        "draft_round": rnd,
        "draft_type": "junreg",
        "query_type": "year_round",
    }
    html = get(DRAFT_URL, tag=f"draft_{year}_r{rnd}", params=params)
    if not html:
        return []
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return []  # no tables on the page
    if not tables:
        return []
    df = tables[0]
    needed = {"OvPck", "Tm", "Name", "Pos", "Type", "Drafted Out of"}
    if not needed.issubset(df.columns):
        return []

    picks = []
    for _, r in df.iterrows():
        ov = r.get("OvPck")
        try:
            overall = int(ov)
        except (TypeError, ValueError):
            continue  # repeated header / blank separator rows
        name = _clean_name(r.get("Name"))
        if not name:
            continue
        rnd_cell = _cell(r.get("Rnd"))
        picks.append({
            "year": year,
            "overall": overall,
            "round": int(rnd_cell) if rnd_cell.isdigit() else rnd,
            "team": _team_full(r.get("Tm")),
            "player": name,
            "position": _cell(r.get("Pos")),
            "school": _school(r.get("Drafted Out of")),
            "level": _level(r.get("Type")),
        })
    return picks


def _scrape_picks() -> tuple[list[dict], list[int], list[int]]:
    """Scrape all YEARS x ROUNDS. Returns (picks, years_with_data, years_skipped)."""
    picks, got, skipped = [], [], []
    for year in YEARS:
        year_picks = []
        for rnd in ROUNDS:
            year_picks.extend(_scrape_year(year, rnd))
        if year_picks:
            picks.extend(year_picks)
            got.append(year)
            print(f"   + {year}: {len(year_picks)} picks")
        else:
            skipped.append(year)
            print(f"   ! {year}: no picks parsed — skipped")
    return picks, got, skipped


def _build_tendencies(picks: list[dict]) -> list[dict]:
    """Per-team summary over the scraped picks, one record for each of the 30 clubs."""
    by_team: dict[str, list[dict]] = {t: [] for t in ALL_TEAMS}
    for p in picks:
        by_team.setdefault(p["team"], []).append(p)

    out = []
    for team in ALL_TEAMS:
        tp = by_team.get(team, [])
        n = len(tp)
        levels = Counter(p["level"] for p in tp)
        buckets = Counter(_pos_bucket(p["position"]) for p in tp)
        n_college, n_hs = levels.get("College", 0), levels.get("HS", 0)
        n_pitcher = buckets.get("P", 0)
        n_hitter = n - n_pitcher

        def pct(x):
            return round(100.0 * x / n, 1) if n else 0.0

        recent = sorted(tp, key=lambda p: (-p["year"], p["overall"]))[:5]
        out.append({
            "team": team,
            "n_picks": n,
            "pct_college": pct(n_college),
            "pct_hs": pct(n_hs),
            "pct_pitcher": pct(n_pitcher),
            "pct_hitter": pct(n_hitter),
            # BR's draft table gives a single "P" for pitchers (no L/R handedness),
            # so RHP/LHP are reported jointly under "P"; C/IF/OF split as usual.
            "position_breakdown": {
                "C": buckets.get("C", 0),
                "IF": buckets.get("IF", 0),
                "OF": buckets.get("OF", 0),
                "P": buckets.get("P", 0),
            },
            "recent_first_round": [
                {"year": p["year"], "overall": p["overall"],
                 "player": p["player"], "position": p["position"],
                 "school": p["school"], "level": p["level"]}
                for p in recent
            ],
        })
    return out


def _build_draft_order_2026() -> tuple[list[dict], int | None]:
    """Projected 2026 1st-round order = inverse of 2025 final regular-season standings
    (worst record picks first). Returns (order, standings_year) or ([], None)."""
    year = 2025
    html = get(STANDINGS_URL.format(year=year), tag=f"standings_{year}")
    if not html:
        return [], None
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return [], None

    teams = []
    for t in tables:
        if not {"Tm", "W", "L"}.issubset(t.columns):
            continue
        for _, r in t.iterrows():
            tm = str(r["Tm"]).strip()
            try:
                w, l = int(r["W"]), int(r["L"])
            except (TypeError, ValueError):
                continue
            pct = w / (w + l) if (w + l) else 0.0
            teams.append((tm, w, l, pct))

    # de-dupe (standings tables shouldn't overlap, but be safe) and require all 30.
    seen, uniq = set(), []
    for tm, w, l, pct in teams:
        if tm not in seen:
            seen.add(tm)
            uniq.append((tm, w, l, pct))
    if len(uniq) != 30:
        print(f"   ! standings yielded {len(uniq)} teams (expected 30)")

    # worst win% first; tie-break by more losses (worse), then name for determinism.
    uniq.sort(key=lambda x: (x[3], -x[2], x[0]))
    order = [{"pick": i, "team": tm} for i, (tm, w, l, pct) in enumerate(uniq, start=1)]
    return order, year


def build() -> dict:
    """Scrape everything and write the three JSON files. Returns a summary dict."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Scraping Baseball-Reference draft pages...")
    picks, got, skipped = _scrape_picks()
    picks.sort(key=lambda p: (p["year"], p["round"], p["overall"]))

    (DATA_DIR / "team_draft_history.json").write_text(
        json.dumps(picks, indent=2), encoding="utf-8")

    tendencies = _build_tendencies(picks)
    (DATA_DIR / "team_tendencies.json").write_text(
        json.dumps(tendencies, indent=2), encoding="utf-8")

    print("Scraping 2025 final standings for the 2026 order projection...")
    order, standings_year = _build_draft_order_2026()
    order_doc = {
        "note": (
            "Projected 2026 MLB first-round order. This is a DEFENSIBLE PROJECTION, "
            "not the official order: it is the inverse of the 2025 final regular-season "
            "standings (worst record picks first), scraped from Baseball-Reference. The "
            "real first six picks are set by MLB's draft lottery and are not reflected here."
        ),
        "method": "inverse_of_2025_final_standings",
        "standings_year": standings_year,
        "order": order,
    }
    (DATA_DIR / "draft_order_2026.json").write_text(
        json.dumps(order_doc, indent=2), encoding="utf-8")

    summary = {
        "n_picks": len(picks),
        "years_with_data": got,
        "years_skipped": skipped,
        "n_teams_tendencies": len(tendencies),
        "n_picks_order_2026": len(order),
        "data_dir": str(DATA_DIR),
    }
    print("\nDone.")
    print(f"  team_draft_history.json : {summary['n_picks']} picks "
          f"across {len(got)} years {got}")
    print(f"  team_tendencies.json    : {summary['n_teams_tendencies']} teams")
    print(f"  draft_order_2026.json   : {summary['n_picks_order_2026']} picks")
    if skipped:
        print(f"  GAPS: years skipped -> {skipped}")
    return summary


if __name__ == "__main__":
    build()
