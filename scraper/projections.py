"""Monte Carlo draft projection — writes app/data/projections_2026.csv."""
from __future__ import annotations

import ast
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent / "app" / "data"
sys.path.insert(0, str(ROOT.parent / "app"))
from logic.sim_engine import simulate  # noqa: E402

N_RUNS = 1000
RANDOMNESS = 0.32


def _load_csv(name: str) -> list[dict]:
    fp = DATA_DIR / name
    if not fp.exists():
        return []
    with open(fp, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_json(name: str):
    fp = DATA_DIR / name
    if not fp.exists():
        return None
    return json.loads(fp.read_text(encoding="utf-8"))


def build() -> None:
    raw = _load_csv("consensus_2026.csv")
    if not raw:
        print("   ! consensus_2026.csv not found — skipping projections")
        return

    src_cols = [k for k in raw[0] if k.startswith("src_")]
    players = []
    for r in raw:
        rankings = {}
        for sc in src_cols:
            v = r.get(sc, "")
            if v and str(v).strip():
                try:
                    rankings[sc[4:]] = int(float(v))
                except ValueError:
                    pass
        players.append({
            "player_id": r["player_id"],
            "player": r["player"],
            "position": r.get("position", ""),
            "school": r.get("school", ""),
            "class_level": r.get("class_level", ""),
            "consensus_rank": int(float(r["consensus_rank"])),
            "n_sources": int(float(r.get("n_sources", 0) or 0)),
            "avg_rank": float(r.get("avg_rank", 0) or 0),
            "rankings": rankings,
        })
    board = sorted(players, key=lambda p: p["consensus_rank"])[:80]

    order_rows = _load_csv("draft_order_2026.csv")
    if order_rows:
        order = [{"pick": int(r["pick"]), "team": r["team"]} for r in order_rows]
    else:
        order_doc = _load_json("draft_order_2026.json")
        if not order_doc:
            print("   ! draft_order not found — skipping projections")
            return
        order = order_doc.get("order") or order_doc

    tend_rows = _load_csv("team_tendencies.csv")
    tend = {}
    if tend_rows:
        for r in tend_rows:
            rec = dict(r)
            if "position_breakdown" in rec and isinstance(rec["position_breakdown"], str):
                try:
                    rec["position_breakdown"] = ast.literal_eval(rec["position_breakdown"])
                except Exception:
                    rec["position_breakdown"] = {}
            for k, v in list(rec.items()):
                if k.startswith("pct_") and v:
                    try:
                        fv = float(v)
                        if fv > 1.0:
                            fv /= 100.0
                        rec[k] = fv
                    except ValueError:
                        pass
            tend[rec["team"]] = rec
    else:
        tend_raw = _load_json("team_tendencies.json") or []
        for r in (tend_raw if isinstance(tend_raw, list) else list(tend_raw.values())):
            r = dict(r)
            for k, v in list(r.items()):
                if k.startswith("pct_") and isinstance(v, (int, float)) and v > 1.0:
                    r[k] = v / 100.0
            tend[r["team"]] = r

    by_id = {p["player_id"]: p for p in board}
    pick_team = {s["pick"]: s["team"] for s in order}

    picks_of: dict[str, list[int]] = {}
    for seed in range(N_RUNS):
        for r in simulate(board, order, tend, mode="realistic",
                          randomness=RANDOMNESS, seed=seed):
            picks_of.setdefault(r["player_id"], []).append(r["pick"])

    rows = []
    for pid, picks in picks_of.items():
        p = by_id.get(pid)
        if not p:
            continue
        picks_sorted = sorted(picks)
        top3 = [{"pick": pk, "team": pick_team.get(pk, ""), "pct": round(cnt / len(picks), 2)}
                for pk, cnt in Counter(picks).most_common(3)]
        rows.append({
            "player_id": pid,
            "player": p["player"],
            "position": p["position"],
            "school": p["school"],
            "class_level": p.get("class_level", ""),
            "consensus_rank": p["consensus_rank"],
            "n_sources": p.get("n_sources", 0),
            "p_round1": round(len(picks) / N_RUNS, 3),
            "proj_pick": int(statistics.median(picks_sorted)),
            "proj_mean": round(statistics.mean(picks_sorted), 1),
            "proj_low": picks_sorted[max(0, int(0.10 * len(picks_sorted)) - 1)],
            "proj_high": picks_sorted[min(len(picks_sorted) - 1, int(0.90 * len(picks_sorted)))],
            "landing": str(top3),
        })

    rows.sort(key=lambda r: (r["proj_pick"], -r["p_round1"]))

    if rows:
        fp = DATA_DIR / "projections_2026.csv"
        with open(fp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"   -> wrote app/data/projections_2026.csv ({len(rows)} players)")

    meta_fp = DATA_DIR / "projections_meta.csv"
    with open(meta_fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["runs", "n_picks", "note"])
        w.writeheader()
        w.writerow({
            "runs": N_RUNS,
            "n_picks": len(order),
            "note": f"{N_RUNS:,} Monte Carlo simulations over the real 2026 first-round order.",
        })
    print("   -> wrote app/data/projections_meta.csv")


if __name__ == "__main__":
    build()
