"""GitHub API helpers — read/write saved_drafts.csv from Pyodide (browser)."""
from __future__ import annotations

import base64
import csv
import io
import json
import sys
import uuid

try:
    import config as _cfg
    GITHUB_REPO = _cfg.GITHUB_REPO
    GITHUB_BRANCH = _cfg.GITHUB_BRANCH
    GITHUB_DRAFTS_PATH = _cfg.GITHUB_DRAFTS_PATH
    GITHUB_TOKEN = _cfg.GITHUB_TOKEN
except Exception:
    GITHUB_REPO = "maxquirk/draft"
    GITHUB_BRANCH = "main"
    GITHUB_DRAFTS_PATH = "app/data/saved_drafts.csv"
    GITHUB_TOKEN = ""

_RAW = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{GITHUB_DRAFTS_PATH}"
_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_DRAFTS_PATH}"


def _headers() -> dict:
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}


def _in_pyodide() -> bool:
    return "pyodide" in sys.modules or hasattr(sys, "_pyodide_core_protocol")


_FIELDS = ["draft_id", "draft_name", "author", "saved_at", "mode", "seed", "picks_json"]


def _parse_csv(text: str) -> list[dict]:
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(text.strip()))
        for row in reader:
            rows.append(dict(row))
    except Exception:
        pass
    return rows


def _row_to_csv_line(row: dict) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=_FIELDS, extrasaction="ignore", lineterminator="\n")
    w.writerow(row)
    return buf.getvalue().rstrip("\n")


def _now_utc() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def load_drafts() -> list[dict]:
    """Load all saved drafts from the repo CSV. Returns [] on failure."""
    import time
    url = f"{_RAW}?t={int(time.time())}"
    if _in_pyodide():
        from pyodide.http import pyfetch
        try:
            resp = await pyfetch(url)
            text = await resp.string()
            return _parse_csv(text)
        except Exception:
            return []
    else:
        try:
            import requests
            r = requests.get(url, timeout=8)
            if r.ok:
                return _parse_csv(r.text)
        except Exception:
            pass
        return []


async def save_draft(
    draft_name: str, author: str, mode: str, seed: int, picks: list[dict]
) -> tuple[bool, str]:
    """Append a new draft row to the repo CSV. Returns (success, message)."""
    if not GITHUB_TOKEN:
        return False, "GitHub token not set — add it to app/config.py and redeploy."

    new_row = {
        "draft_id": str(uuid.uuid4())[:8],
        "draft_name": draft_name.strip() or "Untitled",
        "author": author.strip() or "Anonymous",
        "saved_at": _now_utc(),
        "mode": mode,
        "seed": seed,
        "picks_json": json.dumps(picks),
    }

    if not _in_pyodide():
        return False, "Saving only works in the deployed browser app."

    from pyodide.http import pyfetch

    # 1. GET current file to obtain SHA + existing content
    try:
        resp = await pyfetch(_API, headers=_headers())
        data = await resp.json()
        sha = data["sha"]
        raw_b64 = data.get("content", "").replace("\n", "").replace("\r", "")
        current_text = base64.b64decode(raw_b64).decode("utf-8")
    except Exception as e:
        return False, f"Couldn't read repo file: {e}"

    # 2. Append new row
    new_text = current_text.rstrip("\n") + "\n" + _row_to_csv_line(new_row) + "\n"

    # 3. PUT updated file back
    body = json.dumps({
        "message": f"Add mock draft: {new_row['draft_name']} by {new_row['author']}",
        "content": base64.b64encode(new_text.encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": GITHUB_BRANCH,
    })
    try:
        resp = await pyfetch(
            _API,
            method="PUT",
            headers={**_headers(), "Content-Type": "application/json"},
            body=body,
        )
        result = await resp.json()
        if "content" in result:
            return True, f"Draft \"{new_row['draft_name']}\" saved!"
        return False, f"GitHub error: {result.get('message', 'unknown')}"
    except Exception as e:
        return False, f"Save failed: {e}"
