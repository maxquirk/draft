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


def _token_ok() -> bool:
    return bool(GITHUB_TOKEN) and GITHUB_TOKEN != "DRAFT_PAT_PLACEHOLDER"


_FIELDS = ["draft_id", "draft_name", "author", "saved_at", "mode", "seed", "picks_json",
           "upvotes", "downvotes"]


def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _parse_csv(text: str) -> list[dict]:
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(text.strip()))
        for row in reader:
            rows.append(dict(row))
    except Exception:
        pass
    return rows


def _rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=_FIELDS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for row in rows:
        row.setdefault("upvotes", "0")
        row.setdefault("downvotes", "0")
        w.writerow(row)
    return buf.getvalue()


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
    if not _token_ok():
        return False, "Save not configured — GitHub token missing. Contact the site admin."

    new_row = {
        "draft_id": str(uuid.uuid4())[:8],
        "draft_name": draft_name.strip() or "Untitled",
        "author": author.strip() or "Anonymous",
        "saved_at": _now_utc(),
        "mode": mode,
        "seed": seed,
        "picks_json": json.dumps(picks),
        "upvotes": "0",
        "downvotes": "0",
    }

    if not _in_pyodide():
        return False, "Saving only works in the deployed browser app (not local dev)."

    from pyodide.http import pyfetch

    # 1. GET current file to obtain SHA + existing content
    try:
        get_resp = await pyfetch(
            _API,
            method="GET",
            headers={"Authorization": f"token {GITHUB_TOKEN}",
                     "Accept": "application/vnd.github.v3+json"},
        )
        data = await get_resp.json()
        if isinstance(data, dict) and "message" in data:
            return False, f"GitHub error reading file: {data['message']}"
        sha = data["sha"]
        raw_b64 = data.get("content", "").replace("\n", "").replace("\r", "")
        current_text = base64.b64decode(raw_b64).decode("utf-8")
    except Exception as e:
        return False, f"Couldn't read repo file: {e}"

    # 2. Append new row
    new_text = current_text.rstrip("\n") + "\n" + _row_to_csv_line(new_row) + "\n"

    # 3. PUT updated file back
    put_body = json.dumps({
        "message": f"Add mock draft: {new_row['draft_name']} by {new_row['author']}",
        "content": base64.b64encode(new_text.encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": GITHUB_BRANCH,
    })
    try:
        put_resp = await pyfetch(
            _API,
            method="PUT",
            headers={"Authorization": f"token {GITHUB_TOKEN}",
                     "Accept": "application/vnd.github.v3+json",
                     "Content-Type": "application/json"},
            body=put_body,
        )
        result = await put_resp.json()
        if isinstance(result, dict) and "content" in result:
            return True, f"Draft \"{new_row['draft_name']}\" saved!"
        msg = result.get("message", "unknown error") if isinstance(result, dict) else str(result)
        return False, f"GitHub error: {msg}"
    except Exception as e:
        return False, f"Save failed: {e}"


async def vote_draft(draft_id: str, direction: str) -> tuple[bool, str]:
    """Increment upvote or downvote for a draft. direction: 'up' or 'down'."""
    if not _token_ok():
        return False, "Token missing"
    if not _in_pyodide():
        return False, "Voting only works in the deployed browser app."

    from pyodide.http import pyfetch

    try:
        get_resp = await pyfetch(
            _API, method="GET",
            headers={"Authorization": f"token {GITHUB_TOKEN}",
                     "Accept": "application/vnd.github.v3+json"},
        )
        data = await get_resp.json()
        if isinstance(data, dict) and "message" in data:
            return False, f"GitHub error: {data['message']}"
        sha = data["sha"]
        raw_b64 = data.get("content", "").replace("\n", "").replace("\r", "")
        current_text = base64.b64decode(raw_b64).decode("utf-8")
    except Exception as e:
        return False, str(e)

    rows = _parse_csv(current_text)
    updated = False
    for row in rows:
        if row.get("draft_id") == draft_id:
            field = "upvotes" if direction == "up" else "downvotes"
            row[field] = str(_safe_int(row.get(field, 0)) + 1)
            updated = True
            break

    if not updated:
        return False, "Draft not found"

    new_text = _rows_to_csv(rows)
    put_body = json.dumps({
        "message": f"Vote on draft {draft_id}",
        "content": base64.b64encode(new_text.encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": GITHUB_BRANCH,
    })
    try:
        put_resp = await pyfetch(
            _API, method="PUT",
            headers={"Authorization": f"token {GITHUB_TOKEN}",
                     "Accept": "application/vnd.github.v3+json",
                     "Content-Type": "application/json"},
            body=put_body,
        )
        result = await put_resp.json()
        if isinstance(result, dict) and "content" in result:
            return True, "ok"
        msg = result.get("message", "error") if isinstance(result, dict) else str(result)
        return False, msg
    except Exception as e:
        return False, str(e)
