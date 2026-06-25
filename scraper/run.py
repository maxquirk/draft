"""Orchestrate every source adapter -> normalize -> consensus -> write app/data/*.csv.

Run from the project root:  .venv/Scripts/python.exe -m scraper.run
"""
from __future__ import annotations

import csv
import datetime as dt
import importlib
import traceback
from pathlib import Path

from .config import SOURCES, SOURCE_WEIGHTS, SOURCE_NAMES, SOURCE_ACCESS
from .consensus import build_consensus
from .normalize import merge_players

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent / "app" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _write_csv(name: str, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if not rows:
        print(f"   -> (no rows) skipped {name}")
        return
    fp = DATA_DIR / name
    keys = fieldnames or list(rows[0].keys())
    with open(fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> wrote app/data/{name}  ({len(rows)} rows)")


def main() -> None:
    all_rows: list[dict] = []
    report: list[dict] = []

    for modname, meta in SOURCES:
        print(f"\n== {meta.name} ==")
        status, count, error = "ok", 0, ""
        try:
            mod = importlib.import_module(f"scraper.sources.{modname}")
            rows = mod.fetch() or []
            for r in rows:
                r["source"] = meta.key
            all_rows.extend(rows)
            count = len(rows)
            if count == 0:
                status = "empty"
            print(f"   {count} rows")
        except ModuleNotFoundError:
            status, error = "missing", "adapter module not found"
            print("   ! adapter not built yet — skipping")
        except Exception as e:
            status, error = "error", f"{type(e).__name__}: {e}"
            print(f"   ! {error}")
            traceback.print_exc()
        report.append({
            "key": meta.key, "name": meta.name,
            "status": status, "rows": count, "error": error,
        })

    try:
        from .base import quit_driver
        quit_driver()
    except Exception:
        pass

    print(f"\n== Normalizing {len(all_rows)} rows ==")
    players = merge_players(all_rows)
    consensus = build_consensus(players, SOURCE_WEIGHTS)
    print(f"   {len(consensus)} unique players on the consensus board")

    # Flatten per-source rankings into src_* columns
    src_keys = sorted({k for p in consensus for k in (p.get("rankings") or {})})
    base_cols = ["player_id", "player", "position", "school", "class_level", "state",
                 "notes", "consensus_rank", "avg_rank", "median_rank", "best_rank",
                 "worst_rank", "spread", "stdev", "n_sources"]
    src_col_names = [f"src_{k}" for k in src_keys]
    rows_flat = []
    for p in consensus:
        row = {c: p.get(c, "") for c in base_cols}
        ranks = p.get("rankings") or {}
        for k in src_keys:
            row[f"src_{k}"] = ranks.get(k, "")
        rows_flat.append(row)
    _write_csv("consensus_2026.csv", rows_flat, base_cols + src_col_names)

    # Team draft history
    try:
        th = importlib.import_module("scraper.team_history")
        if hasattr(th, "build"):
            print("\n== Building team draft history ==")
            th.build()
    except ModuleNotFoundError:
        print("\n   (team_history not built yet — skipping)")
    except Exception as e:
        print(f"   ! team_history failed: {e}")

    # Real 2026 order
    try:
        from . import draft_order
        print("\n== Writing actual 2026 draft order ==")
        draft_order.build()
    except Exception as e:
        print(f"   ! draft_order failed: {e}")

    # Monte Carlo projections
    try:
        from . import projections
        print("\n== Projecting the draft (Monte Carlo) ==")
        projections.build()
    except Exception as e:
        print(f"   ! projections failed: {e}")

    _write_csv("run_report.csv", [{
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_players": len(consensus),
    }])

    ok = [r["name"] for r in report if r["status"] == "ok"]
    bad = [f"{r['name']} ({r['status']})" for r in report if r["status"] != "ok"]
    print(f"\nDONE. {len(consensus)} players. Sources OK: {', '.join(ok) or 'none'}")
    if bad:
        print(f"Sources with gaps: {', '.join(bad)}")


if __name__ == "__main__":
    main()
