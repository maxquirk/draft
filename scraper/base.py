"""Fetch utilities and the shared data contract for every source adapter.

The contract every adapter in scraper/sources/ must satisfy:

    SOURCE: SourceMeta           # module-level metadata
    def fetch() -> list[dict]    # returns RankingRow dicts (see ranking_row())

A RankingRow is a plain dict with these keys (missing -> None/""):
    source       str   SOURCE.key (filled by run.py if omitted)
    rank         int   1-based board rank
    player       str   raw player name as printed by the source
    position     str   e.g. "SS", "RHP", "C", "OF"
    school       str   college / HS / org name
    class_level  str   "College" | "HS" | "JUCO" | ""   (best-effort)
    state        str   US state / region if available
    notes        str   optional free text (bats/throws/age/etc.)

Adapters should NEVER raise to the orchestrator on a recoverable problem — they
return whatever rows they got (possibly []). run.py records per-source coverage.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "_raw"
RAW_DIR.mkdir(exist_ok=True)

# A normal desktop UA — we identify as a research scraper in the comment trail,
# rate-limit, and only read public ranking data points.
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


@dataclass
class SourceMeta:
    key: str
    name: str
    url: str
    access: str = "free"  # "free" | "paywall"
    weight: float = 1.0   # consensus weighting (paywalled experts can be trusted higher)


def ranking_row(rank, player, position="", school="", class_level="",
                state="", notes="", source="") -> dict:
    return {
        "source": source,
        "rank": int(rank),
        "player": (player or "").strip(),
        "position": (position or "").strip(),
        "school": (school or "").strip(),
        "class_level": (class_level or "").strip(),
        "state": (state or "").strip(),
        "notes": (notes or "").strip(),
    }


# ---------------------------------------------------------------------------
# Plain HTTP with a tiny disk cache (keeps dev iteration cheap and polite).
# ---------------------------------------------------------------------------
def _cache_path(url: str, tag: str = "") -> Path:
    h = hashlib.sha1((tag + url).encode()).hexdigest()[:16]
    return RAW_DIR / f"{tag or 'page'}_{h}.html"


def get(url: str, *, timeout: int = 30, cache: bool = True, tag: str = "",
        params: dict | None = None) -> str | None:
    """GET a URL as text. Returns None on failure (never raises to caller)."""
    cp = _cache_path(url + (json.dumps(params) if params else ""), tag)
    if cache and cp.exists():
        return cp.read_text(encoding="utf-8", errors="ignore")
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, params=params)
        r.raise_for_status()
        text = r.text
        if cache:
            cp.write_text(text, encoding="utf-8", errors="ignore")
        time.sleep(1.0)  # be polite
        return text
    except Exception as e:  # noqa: BLE001 — adapters must degrade, not crash the run
        print(f"   ! get() failed for {url}: {e}")
        return None


def get_json(url: str, *, timeout: int = 30, params: dict | None = None,
             headers: dict | None = None):
    try:
        h = dict(HEADERS)
        if headers:
            h.update(headers)
        r = requests.get(url, headers=h, timeout=timeout, params=params)
        r.raise_for_status()
        time.sleep(0.8)
        return r.json()
    except Exception as e:  # noqa: BLE001
        print(f"   ! get_json() failed for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Selenium (headless Chrome) — only for JS-rendered pages. Lazily created.
# ---------------------------------------------------------------------------
_DRIVER = None


def get_driver():
    """Return a shared headless Chrome driver, or None if unavailable."""
    global _DRIVER
    if _DRIVER is not None:
        return _DRIVER
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1400,2000")
        opts.add_argument(f"--user-agent={UA}")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        _DRIVER = webdriver.Chrome(options=opts)  # Selenium Manager auto-resolves driver
        return _DRIVER
    except Exception as e:  # noqa: BLE001
        print(f"   ! Selenium unavailable ({e}). JS-rendered sources will be skipped.")
        return None


def render(url: str, *, wait: float = 4.0, scroll: bool = True,
           cache: bool = True, tag: str = "") -> str | None:
    """Load a URL in headless Chrome and return the rendered HTML."""
    cp = _cache_path(url, tag or "render")
    if cache and cp.exists():
        return cp.read_text(encoding="utf-8", errors="ignore")
    drv = get_driver()
    if drv is None:
        return None
    try:
        drv.get(url)
        time.sleep(wait)
        if scroll:
            for _ in range(6):
                drv.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.8)
        html = drv.page_source
        if cache:
            cp.write_text(html, encoding="utf-8", errors="ignore")
        return html
    except Exception as e:  # noqa: BLE001
        print(f"   ! render() failed for {url}: {e}")
        return None


def quit_driver():
    global _DRIVER
    if _DRIVER is not None:
        try:
            _DRIVER.quit()
        except Exception:  # noqa: BLE001
            pass
        _DRIVER = None


# ---------------------------------------------------------------------------
# Paywall fetch chain: direct -> Wayback -> archive.today -> removepaywall(render)
# Returns rendered/extracted HTML or None. Best-effort by design.
# ---------------------------------------------------------------------------
def fetch_paywalled(url: str, *, tag: str = "") -> str | None:
    # 1) direct (sometimes the ranking list is in the static HTML even when prose isn't)
    html = get(url, tag=f"{tag}_direct", cache=True)
    if html and len(html) > 5000:
        return html

    # 2) Wayback Machine — most reliable for archived sports articles
    avail = get_json("https://archive.org/wayback/available", params={"url": url})
    snap = (avail or {}).get("archived_snapshots", {}).get("closest", {})
    if snap.get("available") and snap.get("url"):
        wb = get(snap["url"], tag=f"{tag}_wayback", cache=True)
        if wb and len(wb) > 5000:
            return wb

    # 3) archive.today
    at = get(f"https://archive.ph/newest/{url}", tag=f"{tag}_archiveph", cache=True)
    if at and len(at) > 5000:
        return at

    # 4) removepaywall.com via a rendered browser (it fetches client-side)
    rp = render(f"https://www.removepaywall.com/search?url={quote(url, safe='')}",
                wait=6.0, tag=f"{tag}_removepaywall")
    if rp and len(rp) > 5000:
        return rp

    return None
