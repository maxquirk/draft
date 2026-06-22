"""Turn per-source rankings into a single consensus board with disagreement metrics."""
from __future__ import annotations

import statistics


def build_consensus(players: list[dict], source_weights: dict[str, float]) -> list[dict]:
    """Add consensus fields to each player and return them sorted by consensus rank.

    Consensus rank = weighted average of ONLY the boards that actually ranked the
    player (no phantom-rank penalty for boards that didn't). So a player the boards
    place at 6-8 lands at ~6-8 regardless of how many boards skipped him. Coverage
    is used only as a tiebreaker (more boards win ties), not as a penalty. Adds:
        consensus_rank   int (1-based, after sorting)
        avg_rank         float (weighted, available boards only)
        median_rank, best_rank, worst_rank, spread
        stdev            float (volatility / board disagreement)
        n_sources        int
    """
    enriched = []
    for p in players:
        ranks = p["rankings"]
        if not ranks:
            continue
        vals = list(ranks.values())
        weights = [source_weights.get(s, 1.0) for s in ranks]
        avg = sum(v * w for v, w in zip(vals, weights)) / sum(weights)

        enriched.append({
            **p,
            "avg_rank": round(avg, 2),
            "median_rank": round(statistics.median(vals), 1),
            "best_rank": min(vals),
            "worst_rank": max(vals),
            "spread": max(vals) - min(vals),
            "stdev": round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,
            "n_sources": len(ranks),
        })

    # primary: average rank; tiebreakers: more boards, then best single rank
    enriched.sort(key=lambda x: (x["avg_rank"], -x["n_sources"], x["best_rank"]))
    for i, p in enumerate(enriched, 1):
        p["consensus_rank"] = i
    return enriched
