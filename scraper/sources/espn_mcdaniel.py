"""ESPN+ — Kiley McDaniel's 2026 MLB draft rankings (top 150).

The prose around the list is gated, but McDaniel prints the board itself as
plain text inside the article body, grouped under FV (future value) tier
headings. Each tier paragraph is a run of entries like:

    1. Roch Cholowsky (21.3), SS, UCLA 2. Grady Emerson (18.4), SS, ...

i.e.  "<rank>. <name> (<age>), <pos>, <school>[, <commit/extra notes>]".

We try the live page first (ESPN sometimes serves the static list to bots,
sometimes returns a 202 wall) and fall back to fetch_paywalled(), which reaches
the Wayback Machine snapshot where the board is fully present.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..base import SourceMeta, fetch_paywalled, get, get_json, ranking_row

SOURCE = SourceMeta(
    key="espn_mcdaniel",
    name="ESPN+ — Kiley McDaniel (Top 150)",
    url="https://www.espn.com/mlb/story/_/id/48778463/2026-mlb-draft-rankings-update-top-150-prospects",
    access="paywall",
    weight=1.3,
)

# Split a tier paragraph at each "<rank>. " boundary (rank not preceded by a
# digit, so we don't split inside an age like "21.3").
_SPLIT = re.compile(r"(?=(?<!\d)\b\d{1,3}\.\s)")
# One entry: rank, name, optional (age), position, then the remainder (school + notes).
_ENTRY = re.compile(
    r"^\s*(?P<rank>\d{1,3})\.\s+"
    r"(?P<name>.+?)"
    r"(?:\s*\((?P<age>\d{1,2}\.\d)\))?\s*,\s*"
    r"(?P<pos>[A-Za-z0-9/+-]{1,8})\s*,\s*"
    r"(?P<rest>.+?)\s*$"
)
# A trailing "(ST)" two-letter state code in the school string.
_STATE = re.compile(r"\(([A-Z]{2})\)")


def _parse(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("div.article-body") or soup.select_one("div.Story__Body")
    if body is None:
        return []

    # Concatenate every paragraph that opens with a rank token; the board spans
    # several FV-tier paragraphs.
    blob = " ".join(
        t for p in body.find_all("p")
        if re.match(r"^\d{1,3}\.\s", (t := p.get_text(" ", strip=True)))
    )
    if not blob:
        return []

    rows, seen = [], set()
    for chunk in _SPLIT.split(blob):
        m = _ENTRY.match(chunk)
        if not m:
            continue
        rank = int(m.group("rank"))
        if rank in seen:
            continue
        seen.add(rank)

        rest = m.group("rest").strip()
        # School is everything up to the first comma; the remainder (commit
        # info, dual position, etc.) becomes notes.
        school, _, extra = rest.partition(",")
        school = school.strip()
        st = _STATE.search(school)
        notes = extra.strip()
        if m.group("age"):
            notes = (notes + f"; age {m.group('age')}").lstrip("; ").strip()

        rows.append(ranking_row(
            rank=rank,
            player=m.group("name").strip(),
            position=m.group("pos").strip(),
            school=school,
            state=st.group(1) if st else "",
            notes=notes,
        ))
    return sorted(rows, key=lambda r: r["rank"])


def fetch() -> list[dict]:
    # 1) direct — the list is occasionally in the static HTML.
    html = get(SOURCE.url, tag="espn_mcdaniel_direct")
    if html:
        rows = _parse(html)
        if rows:
            return rows

    # 2) shared paywall chain.
    html = fetch_paywalled(SOURCE.url, tag="espn_mcdaniel")
    if html:
        rows = _parse(html)
        if rows:
            return rows

    # 3) Wayback CDX — the /wayback/available API often returns an empty
    #    "closest" for ESPN, but the CDX index reliably lists captures. Walk
    #    the newest 200-status snapshots until one parses.
    cdx = get_json("https://web.archive.org/cdx/search/cdx",
                   params={"url": SOURCE.url, "output": "json",
                           "filter": "statuscode:200", "limit": -6})
    for ts, original in [(r[1], r[2]) for r in (cdx or [])[1:]][::-1]:
        wb = get(f"https://web.archive.org/web/{ts}/{original}", tag=f"espn_mcdaniel_cdx_{ts}")
        if wb:
            rows = _parse(wb)
            if rows:
                return rows

    return []
