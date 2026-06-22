"""Turn per-source rankings into a single consensus board with disagreement metrics."""
from __future__ import annotations

import statistics


def build_consensus(players: list[dict], source_weights: dict[str, float]) -> list[dict]:
    """Add consensus fields to each player and return them sorted by consensus rank.

    Consensus rank = weighted average of source ranks. Players ranked by fewer
    sources are penalized slightly via an "unranked" fill so a single-source #1
    doesn't outrank a true consensus top pick. Adds:
        consensus_rank   int (1-based, after sorting)
        avg_rank         float (weighted)
        median_rank      float
        best_rank, worst_rank, spread
        stdev            float (volatility / "helium")
        n_sources        int
    """
    n_total = max(1, len({s for p in players for s in p["rankings"]}))
    # A conservative fill for boards that didn't rank a player at all.
    fill = max((max(p["rankings"].values()) for p in players if p["rankings"]), default=300) + 50

    enriched = []
    for p in players:
        ranks = p["rankings"]
        if not ranks:
            continue
        vals = list(ranks.values())
        weights = [source_weights.get(s, 1.0) for s in ranks]

        # weighted average over sources that ranked him, plus a soft penalty for
        # missing coverage (each missing source contributes `fill` at weight 1).
        missing = n_total - len(ranks)
        w_num = sum(v * w for v, w in zip(vals, weights)) + missing * fill * 1.0
        w_den = sum(weights) + missing * 1.0
        avg = w_num / w_den

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

    enriched.sort(key=lambda x: x["avg_rank"])
    for i, p in enumerate(enriched, 1):
        p["consensus_rank"] = i
    return enriched
