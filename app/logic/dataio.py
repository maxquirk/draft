"""Load the static JSON the scraper produced into pandas frames.

Everything degrades to an empty/typed frame if a file is missing, so the app
boots even before the scraper has ever run (or if a single file failed to write).
This module runs both natively (shiny run) and in the browser (shinylive/Pyodide).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def _read_json(name: str):
    fp = DATA / name
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def report() -> dict:
    return _read_json("run_report.json") or {
        "generated_at": "never", "n_players": 0, "sources": [], "source_meta": {},
    }


@lru_cache(maxsize=1)
def source_meta() -> dict:
    """key -> {name, access, weight}. Falls back to keys seen in the data."""
    meta = report().get("source_meta") or {}
    if meta:
        return meta
    keys = set()
    for p in _read_json("consensus_2026.json") or []:
        keys |= set((p.get("rankings") or {}).keys())
    return {k: {"name": k, "access": "free", "weight": 1.0} for k in sorted(keys)}


@lru_cache(maxsize=1)
def consensus() -> pd.DataFrame:
    """The main board: one row per player, with a column per source rank."""
    rows = _read_json("consensus_2026.json") or []
    if not rows:
        return pd.DataFrame(columns=[
            "consensus_rank", "player", "position", "school", "class_level",
            "state", "avg_rank", "median_rank", "best_rank", "worst_rank",
            "spread", "stdev", "n_sources", "notes", "player_id", "rankings",
        ])
    df = pd.DataFrame(rows)
    # explode the per-source rankings dict into src_<key> integer columns
    smeta = source_meta()
    for key in smeta:
        col = f"src_{key}"
        df[col] = df["rankings"].apply(lambda d, k=key: (d or {}).get(k))
    return df


def source_keys() -> list[str]:
    return list(source_meta().keys())


def source_label(key: str) -> str:
    return (source_meta().get(key) or {}).get("name", key)


@lru_cache(maxsize=1)
def team_history() -> pd.DataFrame:
    rows = _read_json("team_draft_history.json") or []
    cols = ["year", "overall", "round", "team", "player", "position", "school", "level"]
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=cols)


@lru_cache(maxsize=1)
def team_tendencies() -> dict:
    """team_name -> tendency dict, with pct_* normalized to 0..1 fractions.

    The scraper writes a list of records with percentages on a 0..100 scale; we
    key by team and rescale so the simulator (expects fractions) and the strategy
    tab agree on units.
    """
    raw = _read_json("team_tendencies.json") or []
    if isinstance(raw, dict):
        records = list(raw.values())
    else:
        records = raw
    out = {}
    for rec in records:
        rec = dict(rec)
        for k, v in list(rec.items()):
            if k.startswith("pct_") and isinstance(v, (int, float)) and v > 1.0:
                rec[k] = v / 100.0
        out[rec.get("team", "")] = rec
    return out


@lru_cache(maxsize=1)
def draft_order() -> list[dict]:
    d = _read_json("draft_order_2026.json")
    if isinstance(d, dict):
        return d.get("order") or d.get("picks") or []
    return d or []
