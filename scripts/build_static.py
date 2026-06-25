"""Build script: converts app/data/ CSVs and JSONs into JS-friendly JSON files in _site/data/."""
from __future__ import annotations
import ast, csv, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"
OUT  = ROOT / "_site" / "data"
OUT.mkdir(parents=True, exist_ok=True)

SRC_PRIORITY = ["mlb_pipeline", "baseball_america", "overslot"]

def read_csv(name):
    fp = DATA / name
    if not fp.exists():
        return []
    with open(fp, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def read_json(name):
    fp = DATA / name
    if not fp.exists():
        return None
    return json.loads(fp.read_text(encoding="utf-8"))

def write_json(name, data):
    with open(OUT / name, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"  wrote {name}")

# ── consensus.json ──────────────────────────────────────────────────────────
rows = read_csv("consensus_2026.csv")
src_keys_all = [k[4:] for k in (rows[0].keys() if rows else []) if k.startswith("src_")]
ordered = [k for k in SRC_PRIORITY if k in src_keys_all] + [k for k in src_keys_all if k not in SRC_PRIORITY]

consensus = []
for r in rows:
    sources = {}
    for k in ordered:
        v = r.get(f"src_{k}", "")
        if v and str(v).strip() not in ("", "nan"):
            try:
                sources[k] = int(float(v))
            except ValueError:
                pass
    consensus.append({
        "player_id": r["player_id"],
        "player": r["player"],
        "position": r.get("position", ""),
        "school": r.get("school", ""),
        "class_level": r.get("class_level", ""),
        "state": r.get("state", ""),
        "notes": r.get("notes", ""),
        "consensus_rank": int(float(r["consensus_rank"])),
        "avg_rank": round(float(r.get("avg_rank") or 0), 2),
        "best_rank": int(float(r.get("best_rank") or 0)),
        "worst_rank": int(float(r.get("worst_rank") or 0)),
        "stdev": round(float(r.get("stdev") or 0), 2),
        "n_sources": int(float(r.get("n_sources") or 0)),
        "sources": sources,
    })
write_json("consensus.json", {"players": consensus, "source_keys": ordered})

# ── draft_order.json ────────────────────────────────────────────────────────
order_raw = read_json("draft_order_2026.json")
order = order_raw.get("order", []) if order_raw else []
write_json("draft_order.json", order)

# ── projections.json ────────────────────────────────────────────────────────
meta_rows = read_csv("projections_meta.csv")
meta = meta_rows[0] if meta_rows else {}
proj_rows = read_csv("projections_2026.csv")
players_proj = []
for r in proj_rows:
    landing_raw = r.get("landing", "[]")
    try:
        landing = ast.literal_eval(landing_raw)
    except Exception:
        landing = []
    players_proj.append({
        "player_id": r["player_id"],
        "player": r["player"],
        "position": r.get("position", ""),
        "school": r.get("school", ""),
        "consensus_rank": int(float(r.get("consensus_rank") or 0)),
        "proj_pick": int(float(r.get("proj_pick") or 0)),
        "proj_low": int(float(r.get("proj_low") or 0)),
        "proj_high": int(float(r.get("proj_high") or 0)),
        "landing": [{"pick": l["pick"], "team": l["team"], "pct": round(float(l["pct"]), 2)} for l in landing],
    })
write_json("projections.json", {"runs": int(meta.get("runs", 0)), "players": players_proj})

# ── tendencies.json ─────────────────────────────────────────────────────────
tend_rows = read_csv("team_tendencies.csv")
tendencies = {}
for r in tend_rows:
    # Build position breakdown from individual pb_* columns (avoids Python-dict-literal parsing)
    pb = {}
    for pos in ("C", "IF", "OF", "P"):
        v = r.get(f"pb_{pos}", "")
        if v and v.strip():
            try:
                pb[pos] = int(float(v))
            except ValueError:
                pass
    team = r.get("team", "")
    # CSV stores pct as 0-100; divide by 100 so JS can use them as 0-1 fractions
    tendencies[team] = {
        "n_picks": int(float(r.get("n_picks") or 0)),
        "pct_college": round(float(r.get("pct_college") or 0) / 100, 4),
        "pct_hs": round(float(r.get("pct_hs") or 0) / 100, 4),
        "pct_pitcher": round(float(r.get("pct_pitcher") or 0) / 100, 4),
        "position_breakdown": pb,
    }
write_json("tendencies.json", tendencies)

# ── history.json ────────────────────────────────────────────────────────────
hist_rows = read_csv("team_draft_history.csv")
history = []
for r in hist_rows:
    try:
        year = int(float(r.get("year") or 0))
        overall = int(float(r.get("overall") or 0))
    except Exception:
        year, overall = 0, 0
    history.append({
        "year": year,
        "overall": overall,
        "round": r.get("round", ""),
        "team": r.get("team", ""),
        "player": r.get("player", ""),
        "position": r.get("position", ""),
        "school": r.get("school", ""),
        "level": r.get("level", ""),
    })
write_json("history.json", history)

# ── grades.json ─────────────────────────────────────────────────────────────
grade_rows = read_csv("player_grades_2026.csv")
grades = {}
for r in grade_rows:
    grades[r["player_id"]] = {k: v for k, v in r.items() if k not in ("player_id",)}
write_json("grades.json", grades)

# ── stats.json ──────────────────────────────────────────────────────────────
stat_rows = read_csv("player_stats_2026.csv")
stats = {}
for r in stat_rows:
    stats[r["player_id"]] = {k: v for k, v in r.items() if k not in ("player_id",)}
write_json("stats.json", stats)

print("Build complete.")
