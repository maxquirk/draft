"""Parse scouting grades, bios, and physical info from the MLB.com draft board page.

The main board page at https://www.mlb.com/milb/prospects/2026/draft/ embeds all
200 players' scouting grades and writeups in the Apollo cache payload via
prospectBio[0].contentText — no individual page fetches needed (uses mlb_pipeline cache).

Grade text (batters):  "Scouting grades: Hit: 60 | Power: 55 | Run: 55 | Arm: 60 | Field: 60 | Overall: 65"
Grade text (pitchers): "Scouting grades: Fastball: 70 | Slider: 55 | Changeup: 55 | Control: 55 | Overall: 60"

Run standalone:  python -m scraper.grades
"""
from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

from .base import get

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "app" / "data"
BOARD_URL = "https://www.mlb.com/milb/prospects/2026/draft/"

_COLS = [
    "player_id", "player", "mlb_id",
    "fv", "hit", "power", "run", "arm", "field",
    "fb_grade", "fb_velo", "cb_grade", "sl_grade", "ch_grade", "control",
    "height", "weight", "bats", "throws",
    "writeup", "commits_to",
]

_COMMIT_RE = re.compile(
    r"committed? to ([A-Z][A-Za-z &'.\-]{3,50}?)(?:\.|,|\s+for|\s+where|\s+to play|\s+this fall|\s+in the fall)",
    re.I,
)


def _extract_cache(page: str) -> dict:
    for blob in re.findall(r'data-init-state="(.*?)"\s*>', page, flags=re.DOTALL):
        try:
            state = json.loads(html.unescape(blob))
            payload = state.get("payload")
            if isinstance(payload, dict) and "ROOT_QUERY" in payload:
                return payload
        except Exception:
            pass
    return {}


def _parse_grades(content_text: str) -> dict:
    """Parse grade integers from the scouting grades line.

    The grades are formatted as "<strong>Scouting grades:</strong> Hit: 60 | Power: 55 | ..."
    so we strip HTML tags first before searching.
    """
    label_map = {
        "hit": "hit", "power": "power", "run": "run", "arm": "arm",
        "field": "field", "defense": "field", "speed": "run",
        "fastball": "fb_grade", "curveball": "cb_grade", "curve": "cb_grade",
        "slider": "sl_grade", "changeup": "ch_grade", "change": "ch_grade",
        "control": "control", "command": "control",
        "overall": "fv",
    }
    grades: dict = {}
    # Strip tags so "</strong> Hit: 60" becomes " Hit: 60"
    flat = re.sub(r"<[^>]+>", " ", content_text)
    grades_line = re.search(r"Scouting grades:([^\n]{10,300})", flat)
    if not grades_line:
        return grades
    for m in re.finditer(r"(\w[\w /]+?):\s*(\d{2,3})", grades_line.group(1)):
        label, val = m.group(1).strip().lower(), int(m.group(2))
        key = label_map.get(label)
        if key and 20 <= val <= 100:
            grades[key] = val
    return grades


def _clean_writeup(content_text: str) -> str:
    """Strip HTML, video link, and grades line — return plain prose."""
    text = re.sub(r"<p[^>]*>.*?Video scouting report.*?</p>", "", content_text, flags=re.I | re.S)
    text = re.sub(r"<p[^>]*>.*?Scouting grades:.*?</p>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:3000]


def _parse_commit(bio_text: str, person: dict) -> str:
    edu = person.get("education") or {}
    colleges = edu.get("colleges") or []
    if colleges and isinstance(colleges, list) and isinstance(colleges[0], dict):
        name = colleges[0].get("name", "").strip()
        if name:
            return name
    m = _COMMIT_RE.search(bio_text)
    return m.group(1).strip() if m else ""


def build() -> None:
    """Parse grades + bios from the cached MLB.com board page."""
    page = get(BOARD_URL, tag="mlb_pipeline", cache=True)
    if not page:
        print("   ! Could not fetch MLB.com board page")
        return

    cache = _extract_cache(page)
    if not cache:
        print("   ! No Apollo cache found in page")
        return

    rq = cache.get("ROOT_QUERY", {})
    entries: list[dict] = []
    for k, v in rq.items():
        if "getPlayerRankingsFromSelection" in k and isinstance(v, list):
            entries.extend(v)

    if not entries:
        print("   ! No ranking entries found in cache")
        return

    # player name → player_id from consensus CSV
    id_map: dict[str, str] = {}
    consensus_fp = DATA / "consensus_2026.csv"
    if consensus_fp.exists():
        with open(consensus_fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                id_map[row.get("player", "").strip()] = row.get("player_id", "")

    rows: list[dict] = []
    found_grades = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        pe = entry.get("playerEntity") or {}
        player_ref = (pe.get("player") or {}).get("__ref", "")
        person = cache.get(player_ref) if player_ref else {}
        if not isinstance(person, dict):
            continue

        name = " ".join(
            p for p in (person.get("useName"), person.get("useLastName")) if p
        ).strip()
        if not name:
            continue

        mlb_id = str(person.get("id", "")).strip()
        pos = pe.get("position") or (person.get("primaryPosition") or {}).get("abbreviation", "")

        bio_list = pe.get("prospectBio") or []
        content_text = bio_list[0].get("contentText", "") if bio_list else ""

        grades = _parse_grades(content_text) if content_text else {}
        clean_text = _clean_writeup(content_text) if content_text else ""
        commit = _parse_commit(clean_text, person)

        if grades:
            found_grades += 1

        # FB velocity: look for velocity range in pitcher writeups
        fb_velo = ""
        is_pitcher = any(p in (pos or "").upper() for p in ("RHP", "LHP", "P"))
        if is_pitcher and clean_text:
            velo_m = re.search(r"\b(9[0-9][-–]\d{2,3}|1[0-1][0-9])\s*(?:mph)?", clean_text, re.I)
            if velo_m:
                fb_velo = velo_m.group(1)

        rows.append({
            "player_id": id_map.get(name, ""),
            "player": name,
            "mlb_id": mlb_id,
            "fv": grades.get("fv", ""),
            "hit": grades.get("hit", ""),
            "power": grades.get("power", ""),
            "run": grades.get("run", ""),
            "arm": grades.get("arm", ""),
            "field": grades.get("field", ""),
            "fb_grade": grades.get("fb_grade", ""),
            "fb_velo": fb_velo,
            "cb_grade": grades.get("cb_grade", ""),
            "sl_grade": grades.get("sl_grade", ""),
            "ch_grade": grades.get("ch_grade", ""),
            "control": grades.get("control", ""),
            "height": person.get("height", ""),
            "weight": person.get("weight", ""),
            "bats": person.get("batSideCode", ""),
            "throws": person.get("pitchHandCode", ""),
            "writeup": clean_text,
            "commits_to": commit,
        })

    out_fp = DATA / "player_grades_2026.csv"
    with open(out_fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> wrote app/data/player_grades_2026.csv  ({len(rows)} players, {found_grades} with grades)")


if __name__ == "__main__":
    build()
