"""Mock-draft engine: consensus board x pick order x team tendencies.

Pure Python so it can be unit-tested and run identically natively or in Pyodide.
Lower rank numbers are better throughout.
"""
from __future__ import annotations

import random

PITCHERS = {"RHP", "LHP", "P"}


def _pos_group(pos: str) -> str:
    pos = (pos or "").upper()
    if pos in PITCHERS:
        return "P"
    if pos in {"C"}:
        return "C"
    if pos in {"OF"}:
        return "OF"
    return "IF"  # SS/2B/3B/1B/IF/DH/UTIL default


def _need_factor(team_tend: dict, player: dict, taken_groups: dict) -> float:
    """Return a multiplier (<1 = team favors this player) from historical lean.

    Combines pitcher/hitter lean and position-group lean, then mildly discounts a
    group the team has already addressed earlier in this same mock.
    """
    if not team_tend:
        return 1.0
    grp = _pos_group(player.get("position", ""))
    is_pitcher = grp == "P"

    # pitcher vs hitter lean, centered at 0.5 (league-ish baseline)
    pct_p = float(team_tend.get("pct_pitcher", 0.5) or 0.5)
    lean = pct_p if is_pitcher else (1.0 - pct_p)
    factor = 1.0 - 0.18 * (lean - 0.5)  # +-9% pull

    # granular position-group lean from the team's historical breakdown
    pb = team_tend.get("position_breakdown") or {}
    total = sum(pb.values()) or 1
    grp_share = pb.get(grp, 0) / total
    factor *= 1.0 - 0.12 * (grp_share - 0.25)

    # diminishing return on a group already taken this mock
    factor *= 1.0 + 0.06 * taken_groups.get(grp, 0)
    return factor


def simulate(board: list[dict], order: list[dict], tendencies: dict, *,
             mode: str = "realistic", randomness: float = 0.15, seed: int = 0,
             locked: dict | None = None) -> list[dict]:
    """Run a mock draft.

    board       consensus players (need consensus_rank, player, position, school)
    order       [{pick, team}, ...]
    tendencies  team_name -> tendency dict (from team_tendencies.json)
    mode        "bpa" (pure consensus) | "team_need" | "realistic" (need + noise)
    locked      {pick_number: player_id} forced picks the user made manually
    """
    rng = random.Random(seed)
    locked = locked or {}
    avail = {p["player_id"]: p for p in board}
    taken_groups: dict[str, dict] = {}  # team -> {group: count}
    results = []

    for slot in order:
        pick_no, team = slot.get("pick"), slot.get("team", "")
        forced = locked.get(pick_no) or locked.get(str(pick_no))
        chosen = None
        is_manual = False

        if forced and forced in avail:
            chosen = avail[forced]
            is_manual = True
        elif avail:
            tg = taken_groups.setdefault(team, {})
            scored = []
            for p in avail.values():
                cr = p.get("consensus_rank", 9999)
                if mode == "bpa":
                    score = cr
                else:
                    score = cr * _need_factor(tendencies.get(team, {}), p, tg)
                    if mode == "realistic" and randomness > 0:
                        score *= 1.0 + rng.uniform(-randomness, randomness)
                scored.append((score, p))
            scored.sort(key=lambda x: x[0])
            chosen = scored[0][1]

        if chosen is None:
            continue
        del avail[chosen["player_id"]]
        grp = _pos_group(chosen.get("position", ""))
        taken_groups.setdefault(team, {}).setdefault(grp, 0)
        taken_groups[team][grp] += 1

        cr = chosen.get("consensus_rank")
        results.append({
            "pick": pick_no, "team": team,
            "player": chosen.get("player", ""),
            "position": chosen.get("position", ""),
            "school": chosen.get("school", ""),
            "class_level": chosen.get("class_level", ""),
            "consensus_rank": cr,
            "value": (cr - pick_no) if isinstance(cr, (int, float)) and pick_no else None,
            "player_id": chosen["player_id"],
            "manual": is_manual,
        })
    return results
