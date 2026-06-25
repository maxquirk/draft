"""Cross-source player identity: canonicalize names and merge the same player
appearing on multiple boards (with slightly different spellings) into one record.
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}

# Map the many position spellings sources use to a compact canonical set.
_POS_MAP = {
    "rhp": "RHP", "rhs": "RHP", "rhsp": "RHP", "rhrp": "RHP", "p": "RHP",
    "lhp": "LHP", "lhsp": "LHP", "lhrp": "LHP",
    "ss": "SS", "shortstop": "SS",
    "2b": "2B", "secondbase": "2B", "second base": "2B",
    "3b": "3B", "thirdbase": "3B", "third base": "3B",
    "1b": "1B", "firstbase": "1B", "first base": "1B",
    "c": "C", "catcher": "C",
    "of": "OF", "cf": "OF", "rf": "OF", "lf": "OF", "outfield": "OF", "outfielder": "OF",
    "if": "IF", "infield": "IF", "inf": "IF",
    "util": "UTIL", "dh": "DH", "2way": "2WAY", "two-way": "2WAY",
}

_HS_HINTS = re.compile(r"\b(hs|high school|prep|academy|christian|catholic|college prep)\b", re.I)
_JUCO_HINTS = re.compile(r"\b(jc|juco|cc|community college|junior college)\b", re.I)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def canon_name(name: str) -> str:
    """A normalized matching key: lowercase, no accents/punct, no suffix.

    Periods are deleted (not spaced) so initials collapse: "A.J." -> "aj",
    matching a source that prints "AJ". Remaining punctuation becomes spaces.
    """
    s = strip_accents(name or "").lower().replace(".", "")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    parts = [p for p in s.split() if p and p not in _SUFFIXES]
    return " ".join(parts)


def norm_position(pos: str) -> str:
    p = (pos or "").strip().lower().replace("/", " ").split()
    if not p:
        return ""
    first = p[0]
    return _POS_MAP.get(first, _POS_MAP.get((pos or "").strip().lower(), (pos or "").strip().upper()))


def infer_class(school: str, given: str = "") -> str:
    if given:
        g = given.strip().lower()
        if g.startswith("hs") or "high" in g:
            return "HS"
        if "juco" in g or "jc" in g:
            return "JUCO"
        if g.startswith("col") or g in {"college", "4yr", "university"}:
            return "College"
    if _JUCO_HINTS.search(school or ""):
        return "JUCO"
    if _HS_HINTS.search(school or ""):
        return "HS"
    return ""


def _best(values: list[str]) -> str:
    """Most common non-empty value."""
    vals = [v for v in values if v]
    if not vals:
        return ""
    return max(set(vals), key=vals.count)


def _likely_same(ka: str, kb: str, rows_a: list[dict], rows_b: list[dict]) -> bool:
    """Decide if two name clusters are the same player.

    Pure name similarity misses nicknames whose spelling differs a lot
    (Eric "EJ" Booth vs Eric Booth Jr.; "EJ Booth" vs "Eric Booth"), so we add
    structural rules confirmed by school. Different last names stay strict.
    """
    ta, tb = ka.split(), kb.split()
    if not ta or not tb:
        return False
    if ta[-1] != tb[-1]:
        # different surnames: only a near-identical full string (typo/accent)
        return fuzz.token_sort_ratio(ka, kb) >= 95
    # same surname:
    if ta[0] == tb[0]:
        return True  # first + last match -> middle name / nickname / suffix differences
    if ta[0][0] == tb[0][0]:  # same first initial (Eric vs EJ)
        sa, sb = _best([r["school"] for r in rows_a]), _best([r["school"] for r in rows_b])
        if sa and sb and fuzz.partial_ratio(sa.lower(), sb.lower()) >= 80:
            return True
    return fuzz.token_sort_ratio(ka, kb) >= 93


def merge_players(rows: list[dict], *, fuzz_threshold: int = 93) -> list[dict]:
    """Group RankingRows into one record per player across sources.

    Returns a list of player dicts:
        {player, player_id, position, school, class_level, state,
         rankings: {source: rank, ...}}
    """
    # cluster by exact canonical name first
    clusters: dict[str, list[dict]] = {}
    for r in rows:
        clusters.setdefault(canon_name(r["player"]), []).append(r)

    # merge clusters that are the same player (typos, nicknames, suffixes) using
    # name structure + school confirmation, not a single similarity threshold.
    keys = list(clusters)
    merged_into: dict[str, str] = {}
    for i, a in enumerate(keys):
        if a in merged_into:
            continue
        for b in keys[i + 1:]:
            if b in merged_into:
                continue
            if _likely_same(a, b, clusters[a], clusters[b]):
                clusters[a].extend(clusters[b])
                merged_into[b] = a
    for b, a in merged_into.items():
        clusters.pop(b, None)

    players = []
    for idx, (key, group) in enumerate(
        sorted(clusters.items(), key=lambda kv: min(r["rank"] for r in kv[1]))
    ):
        positions = [norm_position(r["position"]) for r in group]
        schools = [r["school"] for r in group]
        school = _best(schools)
        class_level = _best([r["class_level"] for r in group]) or infer_class(school)
        mlb_ids = [r.get("mlb_id", "") for r in group if r.get("mlb_id")]
        players.append({
            "player_id": f"p{idx:04d}",
            "player": _best([r["player"] for r in group]) or group[0]["player"],
            "position": _best(positions),
            "school": school,
            "class_level": class_level,
            "state": _best([r["state"] for r in group]),
            "notes": _best([r["notes"] for r in group]),
            "mlb_id": mlb_ids[0] if mlb_ids else "",
            "rankings": {r["source"]: r["rank"] for r in sorted(group, key=lambda x: x["rank"])},
        })
    return players
