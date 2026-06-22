"""MLB.com Pipeline — 2026 Draft top-200 prospects.

The public React app at https://www.mlb.com/milb/prospects/2026/draft/ renders
client-side, but the page ships its Apollo GraphQL cache pre-populated in the
static HTML: a `<span data-init-state="…">` whose HTML-entity-encoded JSON
contains a `payload` with the full board. Inside ROOT_QUERY,
`getPlayerRankingsFromSelection(slug:"sel-pr-2026-draft")` is paginated into
skip=0/100/200 chunks (100 + 100 + 0 = 200 entries). Each RankedPlayerEntity
carries rank + position and a `player.__ref` pointing at a `Person:<id>` entity
elsewhere in the payload, which holds the name, school, and home state.

So we just GET the page (cached, static) and parse the embedded payload — no
headless render and no live GraphQL call needed. The data-graph.mlb.com GraphQL
endpoint is the live backend if this embedding ever disappears.
"""
from __future__ import annotations

import html
import json
import re

from ..base import SourceMeta, get, ranking_row

URL = "https://www.mlb.com/milb/prospects/2026/draft/"
SOURCE = SourceMeta("mlb_pipeline", "MLB.com Pipeline", URL, "free")


def _extract_payload(page: str) -> dict | None:
    """Pull the Apollo cache payload out of the data-init-state span."""
    for blob in re.findall(r'data-init-state="(.*?)"\s*>', page, flags=re.DOTALL):
        if "RankedPlayerEntity" not in blob:
            continue
        state = json.loads(html.unescape(blob))
        payload = state.get("payload")
        if isinstance(payload, dict) and "ROOT_QUERY" in payload:
            return payload
    return None


def _school_and_class(person: dict) -> tuple[str, str, str]:
    """Return (school, class_level, state) from a Person's education block.

    Colleges win over high schools when both are listed (a college commit/player
    is described by the college). state comes from the high school record, which
    is the only education entry that carries a US state.
    """
    edu = person.get("education") or {}
    colleges = edu.get("colleges") or []
    highschools = edu.get("highschools") or []

    state = ""
    if highschools and isinstance(highschools[0], dict):
        state = highschools[0].get("state") or ""

    if colleges and isinstance(colleges[0], dict) and colleges[0].get("name"):
        return colleges[0]["name"], "College", state
    if highschools and isinstance(highschools[0], dict) and highschools[0].get("name"):
        return highschools[0]["name"], "HS", state
    return "", "", state


def fetch() -> list[dict]:
    page = get(URL, tag="mlb_pipeline")
    if not page:
        print("   ! mlb_pipeline: could not fetch the prospects page")
        return []

    payload = _extract_payload(page)
    if not payload:
        print("   ! mlb_pipeline: no ranking payload embedded in the page")
        return []

    # Gather every ranked entry across the skip=0/100/200 pagination chunks.
    entries: list[dict] = []
    for key, value in payload["ROOT_QUERY"].items():
        if key.startswith("getPlayerRankingsFromSelection") and isinstance(value, list):
            entries.extend(value)

    rows: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        pe = entry.get("playerEntity") or {}
        ref = (pe.get("player") or {}).get("__ref")
        person = payload.get(ref) if ref else None
        if not isinstance(person, dict):
            continue  # one missing player shouldn't drop the rest of the board

        name = " ".join(
            part for part in (person.get("useName"), person.get("useLastName")) if part
        ).strip() or person.get("boxscoreName", "")
        if not name:
            continue

        school, class_level, state = _school_and_class(person)
        bats = person.get("batSideCode") or ""
        throws = person.get("pitchHandCode") or ""
        notes = f"B/T: {bats}/{throws}" if (bats or throws) else ""

        rows.append(ranking_row(
            rank=entry.get("rank"),
            player=name,
            position=pe.get("position") or (person.get("primaryPosition") or {}).get("abbreviation", ""),
            school=school,
            class_level=class_level,
            state=state,
            notes=notes,
            source=SOURCE.key,
        ))

    rows.sort(key=lambda r: r["rank"])
    return rows
