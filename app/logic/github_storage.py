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

# Session cache. Populated on first load; SHA populated after first write so
# subsequent writes skip the GET round-trip entirely.
_cache: dict | None = None  # {"rows": list[dict], "sha": str | None}


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


def _extract_sha(put_result: dict) -> str | None:
    try:
        return put_result["content"]["sha"] if "content" in put_result else None
    except Exception:
        return None


async def _api_get():
    """GET the file via GitHub API. Returns (sha, rows) or raises."""
    from pyodide.http import pyfetch
    resp = await pyfetch(
        _API, method="GET",
        headers={"Authorization": f"token {GITHUB_TOKEN}",
                 "Accept": "application/vnd.github.v3+json"},
    )
    data = await resp.json()
    if isinstance(data, dict) and "message" in data:
        raise RuntimeError(f"GitHub error: {data['message']}")
    sha = data["sha"]
    raw_b64 = data.get("content", "").replace("\n", "").replace("\r", "")
    rows = _parse_csv(base64.b64decode(raw_b64).decode("utf-8"))
    return sha, rows


async def _api_put(rows: list[dict], sha: str, message: str) -> str:
    """PUT rows back to the repo. Returns new SHA or raises."""
    from pyodide.http import pyfetch
    body = json.dumps({
        "message": message,
        "content": base64.b64encode(_rows_to_csv(rows).encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": GITHUB_BRANCH,
    })
    resp = await pyfetch(
        _API, method="PUT",
        headers={"Authorization": f"token {GITHUB_TOKEN}",
                 "Accept": "application/vnd.github.v3+json",
                 "Content-Type": "application/json"},
        body=body,
    )
    result = await resp.json()
    if isinstance(result, dict) and "content" in result:
        # GitHub returns the blob SHA of the new commit tree entry, not the file SHA.
        # We'll need a fresh GET next write; set sha to None to signal that.
        return result["content"].get("sha", sha)
    msg = result.get("message", "unknown error") if isinstance(result, dict) else str(result)
    raise RuntimeError(f"GitHub error: {msg}")


async def load_drafts(force: bool = False) -> list[dict]:
    """Load saved drafts. Returns from session cache on repeat calls."""
    global _cache
    if not force and _cache is not None:
        return list(_cache["rows"])

    # First load: fetch from raw CDN (no timestamp = CDN-cacheable, fast edge hit)
    if _in_pyodide():
        from pyodide.http import pyfetch
        try:
            resp = await pyfetch(_RAW)
            text = await resp.string()
            rows = _parse_csv(text)
            _cache = {"rows": rows, "sha": None}
            return list(rows)
        except Exception:
            return []
    else:
        try:
            import requests
            r = requests.get(_RAW, timeout=8)
            if r.ok:
                rows = _parse_csv(r.text)
                _cache = {"rows": rows, "sha": None}
                return list(rows)
        except Exception:
            pass
        return []


async def save_draft(
    draft_name: str, author: str, mode: str, seed: int, picks: list[dict]
) -> tuple[bool, str]:
    """Append a new draft row. Returns (success, message)."""
    global _cache
    if not _token_ok():
        return False, "Save not configured — GitHub token missing. Contact the site admin."
    if not _in_pyodide():
        return False, "Saving only works in the deployed browser app (not local dev)."

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

    # Always GET to obtain authoritative SHA before writing
    try:
        sha, rows = await _api_get()
    except Exception as e:
        return False, f"Couldn't read repo file: {e}"

    rows.append(new_row)
    try:
        new_sha = await _api_put(
            rows, sha, f"Add mock draft: {new_row['draft_name']} by {new_row['author']}"
        )
        _cache = {"rows": rows, "sha": new_sha}
        return True, f"Draft \"{new_row['draft_name']}\" saved!"
    except Exception as e:
        return False, f"Save failed: {e}"


async def vote_draft(draft_id: str, direction: str) -> tuple[bool, str]:
    """Increment upvote or downvote for a draft. direction: 'up' or 'down'."""
    global _cache
    if not _token_ok():
        return False, "Token missing"
    if not _in_pyodide():
        return False, "Voting only works in the deployed browser app."

    # Use cached SHA when available to skip the GET round-trip
    if _cache is not None and _cache.get("sha"):
        sha = _cache["sha"]
        rows = [dict(r) for r in _cache["rows"]]
    else:
        try:
            sha, rows = await _api_get()
        except Exception as e:
            return False, str(e)

    updated = False
    for row in rows:
        if row.get("draft_id") == draft_id:
            field = "upvotes" if direction == "up" else "downvotes"
            row[field] = str(_safe_int(row.get(field, 0)) + 1)
            updated = True
            break

    if not updated:
        return False, "Draft not found"

    try:
        new_sha = await _api_put(rows, sha, f"Vote on draft {draft_id}")
        _cache = {"rows": rows, "sha": new_sha}
        return True, "ok"
    except RuntimeError as e:
        # SHA conflict (another vote landed first): force GET and retry once
        if "409" in str(e) or "conflict" in str(e).lower():
            try:
                sha, rows = await _api_get()
                for row in rows:
                    if row.get("draft_id") == draft_id:
                        field = "upvotes" if direction == "up" else "downvotes"
                        row[field] = str(_safe_int(row.get(field, 0)) + 1)
                        break
                new_sha = await _api_put(rows, sha, f"Vote on draft {draft_id}")
                _cache = {"rows": rows, "sha": new_sha}
                return True, "ok"
            except Exception as e2:
                return False, str(e2)
        return False, str(e)
    except Exception as e:
        return False, str(e)
