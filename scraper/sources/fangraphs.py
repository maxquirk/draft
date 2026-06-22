"""FanGraphs "The Board" — 2026 MLB Draft prospect rankings.

The Board (https://www.fangraphs.com/prospects/the-board/2026-mlb-draft/summary)
is a React app fed by a JSON endpoint:

    https://www.fangraphs.com/api/prospects/board/prospects-list-combined?draft=2026mlb

That endpoint returns a flat list of prospect dicts. The board has no single
"overall rank" column for a draft class — players carry a Future Value ("FV")
grade instead — so we sort by FV descending (ties broken by the API's own list
order) and assign 1-based ranks from that, recording the FV in `notes`.

Field names on the combined endpoint are capitalized and a little inconsistent
across board versions, so each value is read through a small list of candidate
keys rather than one fixed key.

NOTE: the whole fangraphs.com domain (homepage, board page, AND the API) sits
behind a Cloudflare interactive challenge ("Just a moment...", cf-mitigated:
challenge). From a residential browser/IP the API returns clean JSON; from a
datacenter/CI IP every request — plain HTTP and headless Chrome alike — is met
with a 403 challenge, and the Wayback Machine has no snapshot of either the new
board page or the JSON API. When blocked we try the API, then a Wayback copy of
the board page, then return [] rather than fabricate a board.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

from ..base import HEADERS, SourceMeta, fetch_paywalled, get_json, ranking_row

# Drop a CSV exported from The Board's "Export Data" button here (any of these names)
# to ingest FanGraphs without fighting Cloudflare. This is the recommended route.
MANUAL_DIR = Path(__file__).resolve().parent.parent / "manual"

API = "https://www.fangraphs.com/api/prospects/board/prospects-list-combined"
BOARD_URL = "https://www.fangraphs.com/prospects/the-board/2026-mlb-draft/summary"

SOURCE = SourceMeta(
    key="fangraphs",
    name="FanGraphs The Board",
    url=BOARD_URL,
    access="free",
)

# Headers that mimic the board's own XHR; helps when the IP is not CF-blocked.
_API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": BOARD_URL,
    "X-Requested-With": "XMLHttpRequest",
}

# Candidate keys per field — FanGraphs board JSON capitalizes names and varies a
# bit between the "scout" and "combined" board flavors.
_NAME_KEYS = ("Name", "PlayerName", "player_name", "name")
_POS_KEYS = ("Pos", "Position", "position", "minorPOS")
_SCHOOL_KEYS = ("School", "Current Team", "Team", "Org", "current_org", "school")
_FV_KEYS = ("FV", "cFV", "Fv", "futureValue")
_AGE_KEYS = ("Age", "age", "cAge")
_RANK_KEYS = ("Ovr_Rank", "Rank", "rank", "Top 100", "draftRank")
_LEVEL_KEYS = ("Current Level", "Level", "minorLevel")


def _first(d: dict, keys: tuple[str, ...]):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _fv_sort_value(fv) -> float:
    """Turn an FV grade ("55", "50+", "45", 60.0) into a sortable number."""
    if fv is None:
        return -1.0
    if isinstance(fv, (int, float)):
        return float(fv)
    m = re.search(r"\d+(?:\.\d+)?", str(fv))
    if not m:
        return -1.0
    val = float(m.group(0))
    if "+" in str(fv):
        val += 0.5  # 50+ sorts just above 50
    return val


def _classify_level(level: str, school: str) -> str:
    """Best-effort College / HS / JUCO label from the board's level/school text."""
    text = f"{level} {school}".lower()
    if "juco" in text or "junior college" in text:
        return "JUCO"
    if re.search(r"\bh\.?s\.?\b|high school", text):
        return "HS"
    if re.search(r"univ|college|state|\bu\b", text):
        return "College"
    return ""


def _extract_records(data) -> list[dict]:
    """Accept either a bare list or a wrapper dict ({data|prospects|rows:[...]})."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("data", "prospects", "rows", "items", "results"):
            inner = data.get(key)
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
    return []


def _rows_from_records(records: list[dict]) -> list[dict]:
    parsed = []
    for rec in records:
        name = _first(rec, _NAME_KEYS)
        if not name:
            continue
        fv = _first(rec, _FV_KEYS)
        explicit_rank = _first(rec, _RANK_KEYS)
        school = _first(rec, _SCHOOL_KEYS) or ""
        level = _first(rec, _LEVEL_KEYS) or ""
        age = _first(rec, _AGE_KEYS)
        notes = "; ".join(
            p for p in (
                f"FV {fv}" if fv is not None else "",
                f"Age {age}" if age is not None else "",
            ) if p
        )
        parsed.append({
            "name": str(name).strip(),
            "position": str(_first(rec, _POS_KEYS) or "").strip(),
            "school": str(school).strip(),
            "class_level": _classify_level(str(level), str(school)),
            "notes": notes,
            "fv_sort": _fv_sort_value(fv),
            "explicit_rank": int(explicit_rank) if isinstance(explicit_rank, (int, float)) else None,
        })

    # Prefer the board's own overall rank when every row has one; otherwise rank
    # by FV descending, keeping the API's list order as the tiebreaker.
    if parsed and all(p["explicit_rank"] for p in parsed):
        parsed.sort(key=lambda p: p["explicit_rank"])
    else:
        parsed.sort(key=lambda p: -p["fv_sort"])  # stable: preserves list order on ties

    rows = []
    for i, p in enumerate(parsed, start=1):
        rows.append(ranking_row(
            rank=p["explicit_rank"] or i,
            player=p["name"],
            position=p["position"],
            school=p["school"],
            class_level=p["class_level"],
            notes=p["notes"],
            source=SOURCE.key,
        ))
    return rows


def _from_api() -> list[dict]:
    # If the user captured a cf_clearance cookie from a browser that passed the
    # Cloudflare challenge, reuse it (it is IP+UA bound, so set FANGRAPHS_UA too if
    # the browser UA differs). Otherwise a plain request that may work off a
    # residential IP that Cloudflare hasn't flagged.
    cc = os.environ.get("FANGRAPHS_CF_CLEARANCE")
    headers = dict(_API_HEADERS)
    if os.environ.get("FANGRAPHS_UA"):
        headers["User-Agent"] = os.environ["FANGRAPHS_UA"]
    cookies = {"cf_clearance": cc} if cc else None
    for params in ({"draft": "2026mlb"}, {"draft": "2026mlb", "type": "draft"}):
        try:
            r = requests.get(API, params=params, headers={**HEADERS, **headers},
                             cookies=cookies, timeout=40)
            if r.status_code == 200 and r.text.strip().startswith(("[", "{")):
                records = _extract_records(r.json())
                if records:
                    return _rows_from_records(records)
        except Exception as e:  # noqa: BLE001
            print(f"   ! fangraphs api: {e}")
    return []


def _from_manual() -> list[dict]:
    """Parse a CSV the user exported from The Board ('Export Data' button)."""
    if not MANUAL_DIR.exists():
        return []
    import pandas as pd
    for fp in sorted(MANUAL_DIR.glob("fangraphs*.csv")):
        try:
            df = pd.read_csv(fp)
            rows = _rows_from_records(df.to_dict("records"))
            if rows:
                print(f"   + fangraphs: loaded {len(rows)} rows from {fp.name}")
                return rows
        except Exception as e:  # noqa: BLE001
            print(f"   ! fangraphs manual csv {fp.name}: {e}")
    return []


def _from_wayback() -> list[dict]:
    """Last resort: an archived board page may embed the prospect JSON inline."""
    page = fetch_paywalled(BOARD_URL, tag="fangraphs")
    if not page:
        return []
    # The React board hydrates from a JSON blob; look for a list of dicts that
    # carries FanGraphs prospect keys.
    for blob in re.findall(r'(\[\{.*?\}\])', page, flags=re.DOTALL):
        if '"FV"' not in blob and '"Pos"' not in blob:
            continue
        try:
            records = _extract_records(json.loads(blob))
        except (ValueError, TypeError):
            continue
        if records:
            return _rows_from_records(records)
    return []


def fetch() -> list[dict]:
    # 1) a CSV the user exported from The Board (most reliable, no CF fight)
    rows = _from_manual()
    if rows:
        return rows
    # 2) the JSON API (works with a cf_clearance cookie or an unflagged IP)
    rows = _from_api()
    if rows:
        return rows
    # 3) an archived copy of the board page
    rows = _from_wayback()
    if rows:
        return rows
    print("   ! fangraphs: Cloudflare-blocked and no manual CSV / archive available. "
          "Export The Board to scraper/manual/fangraphs_board.csv to ingest it.")
    return []
