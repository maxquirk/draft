"""Scrape scouting grades and FV from individual MLB.com draft prospect pages.

Each player's page at https://www.mlb.com/milb/prospects/draft/{slug}-{mlb_id}
embeds an Apollo cache with scouting grades (FV, tool grades, writeup, school commit).

Reads consensus_2026.csv for players with mlb_ids (populated by mlb_pipeline source),
writes app/data/player_grades_2026.csv.

Run standalone:  python -m scraper.grades
"""
from __future__ import annotations

import csv
import html
import json
import re
import time
import unicodedata
from pathlib import Path

from .base import get

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "app" / "data"
BASE_URL = "https://www.mlb.com/milb/prospects/draft"

_COLS = [
    "player_id", "player", "mlb_id", "fv",
    "hit", "power", "run", "arm", "field",
    "fb_grade", "fb_velo", "cb_grade", "sl_grade", "ch_grade", "control",
    "writeup", "commits_to",
]


def _slug(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def _extract_cache(page: str) -> dict:
    for blob in re.findall(r'data-init-state="(.*?)"\s*>', page, flags=re.DOTALL):
        try:
            state = json.loads(html.unescape(blob))
            payload = state.get("payload")
            if isinstance(payload, dict) and len(payload) > 3:
                return payload
        except Exception:
            pass
    return {}


def _is_grade(val) -> bool:
    try:
        g = int(float(val))
        return 20 <= g <= 80
    except (TypeError, ValueError):
        return False


def _find_grades(cache: dict) -> dict:
    grades: dict = {}

    for _key, val in cache.items():
        if not isinstance(val, dict):
            continue

        # Future value
        for f in ("futureValue", "fv", "overallGrade", "grade"):
            if f in val and _is_grade(val[f]) and "fv" not in grades:
                grades["fv"] = int(float(val[f]))

        # Batter tool grades
        tool_map = {
            "hit": ["hit", "hitGrade", "gradeHit", "hitPresentGrade", "hitFutureGrade"],
            "power": ["power", "powerGrade", "gradePower"],
            "run": ["run", "speed", "runGrade", "speedGrade", "gradeSpeed"],
            "arm": ["arm", "armGrade", "gradeArm"],
            "field": ["field", "defense", "fieldGrade", "fieldingGrade", "gradeField"],
        }
        for tool, aliases in tool_map.items():
            if tool not in grades:
                for alias in aliases:
                    if alias in val and _is_grade(val[alias]):
                        grades[tool] = int(float(val[alias]))
                        break

        # Pitcher tool grades
        pitcher_map = {
            "fb_grade": ["fastball", "fastballGrade", "fbGrade"],
            "cb_grade": ["curveball", "curveballGrade", "cbGrade", "curve"],
            "sl_grade": ["slider", "sliderGrade", "slGrade"],
            "ch_grade": ["changeup", "changeupGrade", "chGrade", "change"],
            "control": ["control", "controlGrade", "command", "commandGrade"],
        }
        for tool, aliases in pitcher_map.items():
            if tool not in grades:
                for alias in aliases:
                    if alias in val and _is_grade(val[alias]):
                        grades[tool] = int(float(val[alias]))
                        break

        # FB velocity
        if "fb_velo" not in grades:
            for f in ("fastballVelocity", "velocity", "fbVelocity", "fbVelo"):
                if f in val:
                    v = str(val[f]).strip()
                    if re.match(r"^\d{2,3}(\.\d)?$", v):
                        grades["fb_velo"] = v
                        break

        # Scouting writeup
        if "writeup" not in grades:
            for f in ("scoutingReport", "body", "report", "text", "description"):
                if f in val and isinstance(val[f], str) and len(val[f]) > 80:
                    grades["writeup"] = val[f][:2000]
                    break

        # School commit
        if "commits_to" not in grades:
            for f in ("collegeName", "collegeCommitment", "commitmentSchool", "commit"):
                if f in val and isinstance(val[f], str) and val[f].strip():
                    grades["commits_to"] = val[f].strip()
                    break

    return grades


def build() -> None:
    """Fetch grades for all players that have an mlb_id in consensus_2026.csv."""
    consensus_fp = DATA / "consensus_2026.csv"
    if not consensus_fp.exists():
        print("   ! consensus_2026.csv not found — run scraper.run first")
        return

    players: list[dict] = []
    with open(consensus_fp, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mlb_id = row.get("mlb_id", "").strip()
            if mlb_id and mlb_id not in ("", "nan"):
                players.append({
                    "player_id": row.get("player_id", ""),
                    "player": row.get("player", ""),
                    "mlb_id": mlb_id,
                })

    if not players:
        print("   ! No mlb_ids in consensus_2026.csv — mlb_pipeline scraper must run first")
        return

    print(f"   Fetching grades for {len(players)} players with mlb_ids ...")
    rows: list[dict] = []

    for p in players:
        slug = _slug(p["player"])
        url = f"{BASE_URL}/{slug}-{p['mlb_id']}"
        page = get(url, tag=f"grades_{p['mlb_id']}", cache=True)
        if not page:
            continue

        cache = _extract_cache(page)
        if not cache:
            continue

        g = _find_grades(cache)
        n = sum(1 for k in ("fv", "hit", "power", "fb_grade") if k in g)
        print(f"   {p['player']}: {n} grade fields found")

        rows.append({
            "player_id": p["player_id"],
            "player": p["player"],
            "mlb_id": p["mlb_id"],
            "fv": g.get("fv", ""),
            "hit": g.get("hit", ""),
            "power": g.get("power", ""),
            "run": g.get("run", ""),
            "arm": g.get("arm", ""),
            "field": g.get("field", ""),
            "fb_grade": g.get("fb_grade", ""),
            "fb_velo": g.get("fb_velo", ""),
            "cb_grade": g.get("cb_grade", ""),
            "sl_grade": g.get("sl_grade", ""),
            "ch_grade": g.get("ch_grade", ""),
            "control": g.get("control", ""),
            "writeup": g.get("writeup", ""),
            "commits_to": g.get("commits_to", ""),
        })
        time.sleep(0.3)

    out_fp = DATA / "player_grades_2026.csv"
    with open(out_fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> wrote app/data/player_grades_2026.csv  ({len(rows)} rows)")


if __name__ == "__main__":
    build()
