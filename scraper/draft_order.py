"""The ACTUAL 2026 MLB Draft first-round order (post-lottery), not a projection.

Set by the Dec 9, 2025 draft lottery + competitive-balance picks + CBT/penalty
adjustments. This is final, published, factual data (source: MLB.com draft order
and the 2026 MLB Draft Wikipedia page), so we encode the verified list rather
than scrape a JS-rendered order page on every run. Team names match the keys in
team_tendencies.json so the simulator's team-need weighting maps cleanly.

Covers the full first round (1-25), Prospect Promotion Incentive / penalty picks
(26-28), and Competitive Balance Round A (29-37).
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"

# (pick, team, note) — note is informational (acquisitions, PPI, penalties).
ORDER_2026: list[tuple[int, str, str]] = [
    (1, "Chicago White Sox", "won the 2026 draft lottery"),
    (2, "Tampa Bay Rays", ""),
    (3, "Minnesota Twins", ""),
    (4, "San Francisco Giants", ""),
    (5, "Pittsburgh Pirates", ""),
    (6, "Kansas City Royals", ""),
    (7, "Baltimore Orioles", ""),
    (8, "Athletics", ""),
    (9, "Atlanta Braves", ""),
    (10, "Colorado Rockies", ""),
    (11, "Washington Nationals", ""),
    (12, "Los Angeles Angels", ""),
    (13, "St. Louis Cardinals", ""),
    (14, "Miami Marlins", ""),
    (15, "Arizona Diamondbacks", ""),
    (16, "Texas Rangers", ""),
    (17, "Houston Astros", ""),
    (18, "Cincinnati Reds", ""),
    (19, "Cleveland Guardians", ""),
    (20, "Boston Red Sox", ""),
    (21, "San Diego Padres", ""),
    (22, "Detroit Tigers", ""),
    (23, "Chicago Cubs", ""),
    (24, "Seattle Mariners", ""),
    (25, "Milwaukee Brewers", ""),
    (26, "Atlanta Braves", "Prospect Promotion Incentive (Drake Baldwin, NL ROY)"),
    (27, "New York Mets", "moved back for exceeding the top CBT threshold"),
    (28, "Houston Astros", "Prospect Promotion Incentive (Hunter Brown, top-3 Cy Young)"),
    (29, "San Francisco Giants", "Competitive Balance Round A (acquired from Cleveland)"),
    (30, "Kansas City Royals", "Competitive Balance Round A"),
    (31, "Arizona Diamondbacks", "Competitive Balance Round A"),
    (32, "St. Louis Cardinals", "Competitive Balance Round A"),
    (33, "Tampa Bay Rays", "Competitive Balance Round A (acquired from Baltimore)"),
    (34, "Pittsburgh Pirates", "Competitive Balance Round A"),
    (35, "New York Yankees", "moved back for exceeding the top CBT threshold"),
    (36, "Philadelphia Phillies", "moved back for exceeding the top CBT threshold"),
    (37, "Colorado Rockies", "Competitive Balance Round A"),
]


def build() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": "Actual 2026 MLB Draft first-round order (post Dec 9, 2025 lottery), "
                "including PPI/penalty picks and Competitive Balance Round A.",
        "source": "MLB.com draft order + 2026 MLB Draft (Wikipedia)",
        "order": [{"pick": p, "team": t, "note": n} for p, t, n in ORDER_2026],
    }
    (DATA_DIR / "draft_order_2026.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   -> wrote app/data/draft_order_2026.json ({len(ORDER_2026)} picks, real order)")


if __name__ == "__main__":
    build()
