"""Monte Carlo draft projection: how is each player likely to be drafted?

Runs the mock-draft engine N times over the ACTUAL 2026 first-round order, using
the full consensus board (all big-board rankings) and each team's historical draft
tendencies, with per-run unpredictability. Aggregates, per player:

    p_round1     share of runs in which he was taken in the first round
    proj_pick    median pick across runs where he was taken (his projected slot)
    proj_low/high  10th / 90th percentile of those picks (a realistic range)
    likely_team  the team that drafted him most often, and how often

Writes app/data/draft_projections_2026.json. Precomputed offline because the
shinylive (Pyodide) app can't run thousands of sims in the browser.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent / "app" / "data"
sys.path.insert(0, str(ROOT.parent / "app"))  # import the same engine the app uses
from logic.sim_engine import simulate  # noqa: E402

N_RUNS = 1000
RANDOMNESS = 0.32  # real draft-night uncertainty; wide enough to surface the bubble


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def build() -> None:
    # Only the top of the board can realistically go in round 1; capping the pool
    # keeps the Monte Carlo fast without changing who actually gets drafted.
    board = sorted(_load("consensus_2026.json"), key=lambda p: p["consensus_rank"])[:80]
    order_doc = _load("draft_order_2026.json")
    order = order_doc.get("order") or order_doc

    # team_tendencies.json stores percentages 0..100; the engine (like the app's
    # dataio loader) expects 0..1 fractions. Normalize before scoring.
    tend = {}
    for r in _load("team_tendencies.json"):
        r = dict(r)
        for k, v in list(r.items()):
            if k.startswith("pct_") and isinstance(v, (int, float)) and v > 1.0:
                r[k] = v / 100.0
        tend[r["team"]] = r
    by_id = {p["player_id"]: p for p in board}

    picks_of: dict[str, list[int]] = {}
    teams_of: dict[str, Counter] = {}
    for seed in range(N_RUNS):
        for r in simulate(board, order, tend, mode="realistic",
                          randomness=RANDOMNESS, seed=seed):
            pid = r["player_id"]
            picks_of.setdefault(pid, []).append(r["pick"])
            teams_of.setdefault(pid, Counter())[r["team"]] += 1

    rows = []
    for pid, picks in picks_of.items():
        p = by_id.get(pid)
        if not p:
            continue
        picks_sorted = sorted(picks)
        team, cnt = teams_of[pid].most_common(1)[0]
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
            "likely_team": team,
            "likely_team_pct": round(cnt / len(picks), 2),
        })

    # order by projected slot, then by how often they actually land in R1
    rows.sort(key=lambda r: (r["proj_pick"], -r["p_round1"]))
    out = {
        "runs": N_RUNS,
        "n_picks": len(order),
        "note": (f"{N_RUNS} Monte Carlo drafts over the real 2026 first-round order, "
                 "using the consensus board and each team's 2018-2025 draft tendencies."),
        "players": rows,
    }
    (DATA_DIR / "draft_projections_2026.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   -> wrote app/data/draft_projections_2026.json "
          f"({len(rows)} players projected over {N_RUNS} runs)")


if __name__ == "__main__":
    build()
