"""Load static CSVs from app/data/ into pandas frames.

Degrades to empty typed frames if files are missing.
Runs both natively and in the browser (shinylive/Pyodide).
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def _read_csv(name: str) -> pd.DataFrame | None:
    fp = DATA / name
    if not fp.exists():
        return None
    try:
        return pd.read_csv(fp, encoding="utf-8")
    except Exception:
        return None


@lru_cache(maxsize=1)
def consensus() -> pd.DataFrame:
    """Main board: one row per player, with src_<key> columns for each source rank."""
    df = _read_csv("consensus_2026.csv")
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "consensus_rank", "player", "position", "school", "class_level",
            "state", "avg_rank", "median_rank", "best_rank", "worst_rank",
            "spread", "stdev", "n_sources", "notes", "player_id",
        ])
    # Rebuild a rankings dict from src_* columns so detail cards still work
    src_cols = [c for c in df.columns if c.startswith("src_")]
    def _rankings(row):
        return {c[4:]: int(v) for c in src_cols if not pd.isna(v := row[c])}
    df["rankings"] = df.apply(_rankings, axis=1)
    return df


def source_keys() -> list[str]:
    df = consensus()
    return [c[4:] for c in df.columns if c.startswith("src_")]


def source_label(key: str) -> str:
    return key.replace("_", " ").title()


@lru_cache(maxsize=1)
def team_history() -> pd.DataFrame:
    df = _read_csv("team_draft_history.csv")
    cols = ["year", "overall", "round", "team", "player", "position", "school", "level"]
    return df if df is not None else pd.DataFrame(columns=cols)


@lru_cache(maxsize=1)
def team_tendencies() -> dict:
    """team_name -> tendency dict with pct_* normalized to 0..1 fractions."""
    df = _read_csv("team_tendencies.csv")
    if df is None or df.empty:
        return {}
    out = {}
    for _, rec in df.iterrows():
        rec = rec.to_dict()
        for k, v in list(rec.items()):
            if k.startswith("pct_") and isinstance(v, (int, float)) and v > 1.0:
                rec[k] = v / 100.0
        out[rec.get("team", "")] = rec
    return out


@lru_cache(maxsize=1)
def projections() -> pd.DataFrame:
    df = _read_csv("projections_2026.csv")
    cols = ["proj_pick", "player", "position", "school", "consensus_rank",
            "p_round1", "proj_low", "proj_high", "player_id"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    # landing is stored as a repr string in CSV; parse it back to a list
    if "landing" in df.columns:
        def _parse_landing(v):
            if pd.isna(v) or not v:
                return []
            try:
                return ast.literal_eval(str(v))
            except Exception:
                return []
        df["landing"] = df["landing"].apply(_parse_landing)
    return df


@lru_cache(maxsize=1)
def projections_meta() -> dict:
    fp = DATA / "projections_meta.csv"
    if not fp.exists():
        return {"runs": 0, "note": ""}
    df = pd.read_csv(fp, encoding="utf-8")
    if df.empty:
        return {"runs": 0, "note": ""}
    row = df.iloc[0]
    return {"runs": int(row.get("runs", 0)), "note": str(row.get("note", ""))}


@lru_cache(maxsize=1)
def draft_order() -> list[dict]:
    df = _read_csv("draft_order_2026.csv")
    if df is None or df.empty:
        return []
    return df.to_dict("records")


@lru_cache(maxsize=1)
def player_stats() -> pd.DataFrame:
    """Optional: 2025-season stats for draft prospects. Empty if not yet collected."""
    df = _read_csv("player_stats_2026.csv")
    if df is None or df.empty:
        return pd.DataFrame(columns=["player_id", "player", "stat_type",
                                      "avg", "obp", "slg", "ops", "hr", "rbi", "sb",
                                      "era", "whip", "k_9", "bb_9", "ip", "w", "sv"])
    return df


@lru_cache(maxsize=1)
def player_grades() -> pd.DataFrame:
    """Scouting grades from MLB.com: FV, tool grades, writeup. Empty if not scraped."""
    df = _read_csv("player_grades_2026.csv")
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "player", "mlb_id", "fv", "hit", "power", "run", "arm", "field",
            "fb_grade", "fb_velo", "cb_grade", "sl_grade", "ch_grade", "control",
            "writeup", "commits_to",
        ])
    return df
