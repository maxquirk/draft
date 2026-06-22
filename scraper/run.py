"""Orchestrate every source adapter -> normalize -> consensus -> write app/data/*.json.

Run from the project root:  .venv/Scripts/python.exe -m scraper.run
A source whose module is missing, errors, or returns nothing is skipped and noted
in run_report.json so coverage is always explicit (the app surfaces it).
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import traceback
from pathlib import Path

from .config import SOURCES, SOURCE_WEIGHTS, SOURCE_NAMES, SOURCE_ACCESS
from .consensus import build_consensus
from .normalize import merge_players

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent / "app" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _write(name: str, obj) -> None:
    (DATA_DIR / name).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   -> wrote app/data/{name}")


def main() -> None:
    all_rows: list[dict] = []
    report: list[dict] = []

    for modname, meta in SOURCES:
        print(f"\n== {meta.name} [{meta.access}] ==")
        status, count, error = "ok", 0, ""
        try:
            mod = importlib.import_module(f"scraper.sources.{modname}")
            rows = mod.fetch() or []
            for r in rows:
                r["source"] = meta.key  # authoritative
            all_rows.extend(rows)
            count = len(rows)
            if count == 0:
                status = "empty"
            print(f"   {count} rows")
        except ModuleNotFoundError:
            status, error = "missing", "adapter module not found"
            print("   ! adapter not built yet — skipping")
        except Exception as e:  # noqa: BLE001 — never let one source kill the run
            status, error = "error", f"{type(e).__name__}: {e}"
            print(f"   ! {error}")
            traceback.print_exc()
        report.append({
            "key": meta.key, "name": meta.name, "access": meta.access,
            "weight": meta.weight, "status": status, "rows": count, "error": error,
        })

    # clean up the shared headless browser if any source spun it up
    try:
        from .base import quit_driver
        quit_driver()
    except Exception:  # noqa: BLE001
        pass

    print(f"\n== Normalizing {len(all_rows)} rows across "
          f"{len({r['source'] for r in all_rows})} sources ==")
    players = merge_players(all_rows)
    consensus = build_consensus(players, SOURCE_WEIGHTS)
    print(f"   {len(consensus)} unique players on the consensus board")

    # Optional: refresh team draft history if that module is present.
    try:
        th = importlib.import_module("scraper.team_history")
        if hasattr(th, "build"):
            print("\n== Building team draft history ==")
            th.build()
    except ModuleNotFoundError:
        print("\n   (team_history not built yet — skipping)")
    except Exception as e:  # noqa: BLE001
        print(f"   ! team_history failed: {e}")

    _write("consensus_2026.json", consensus)
    _write("run_report.json", {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_players": len(consensus),
        "sources": report,
        "source_meta": {
            k: {"name": SOURCE_NAMES[k], "access": SOURCE_ACCESS[k], "weight": SOURCE_WEIGHTS[k]}
            for k in SOURCE_NAMES
        },
    })

    ok = [r["name"] for r in report if r["status"] == "ok"]
    bad = [f"{r['name']} ({r['status']})" for r in report if r["status"] != "ok"]
    print(f"\nDONE. {len(consensus)} players. Sources OK: {', '.join(ok) or 'none'}")
    if bad:
        print(f"Sources with gaps: {', '.join(bad)}")


if __name__ == "__main__":
    main()
