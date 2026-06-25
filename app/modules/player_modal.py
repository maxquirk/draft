"""Reusable player detail modal — shown when any player is clicked anywhere in the app."""
from __future__ import annotations

import urllib.parse

import pandas as pd
from shiny import ui

from logic import dataio


def _br_link(name: str) -> ui.Tag:
    encoded = urllib.parse.quote_plus(name)
    url = f"https://www.baseball-reference.com/search/search.fcgi?search={encoded}"
    return ui.tags.a("Baseball-Reference ↗", href=url, target="_blank",
                     class_="btn btn-outline-secondary btn-sm", style="font-size:.8rem;")


def player_modal(player_name: str) -> ui.Tag:
    """Return a fully-populated modal for `player_name`."""
    df = dataio.consensus()
    row_df = df[df["player"] == player_name]
    if row_df.empty:
        return ui.modal(ui.p("Player not found."), title=player_name, easy_close=True)

    r = row_df.iloc[0]
    ranks = r.get("rankings") or {}

    # Source rank chips
    chips = [
        ui.span(f"{dataio.source_label(k)}: #{v}", class_="src-chip")
        for k, v in sorted(ranks.items(), key=lambda kv: kv[1])
    ] if ranks else [ui.span("No source ranks available.", class_="muted")]

    # Projection section
    proj_df = dataio.projections()
    proj_section = ui.div()
    if len(proj_df):
        p_row = proj_df[proj_df["player"] == player_name]
        if len(p_row):
            pr = p_row.iloc[0]
            pr1 = int(round(100 * float(pr["p_round1"])))
            landing = pr.get("landing") or []
            spots = " · ".join(
                f"<b>#{l['pick']}</b> {l['team']} <span class='muted'>{int(round(100*l['pct']))}%</span>"
                for l in landing[:3]
            )
            proj_section = ui.div(
                ui.hr(),
                ui.h4("Draft Projection", style="font-size:.95rem;margin-bottom:.5rem;"),
                ui.div(
                    ui.span(f"Proj. pick #{int(pr['proj_pick'])}", class_="big-chip"),
                    ui.span(f"Range {int(pr['proj_low'])}–{int(pr['proj_high'])}", class_="src-chip"),
                    ui.span(f"Round-1 {pr1}%", class_="src-chip"),
                ),
                ui.p(ui.HTML(f"<span class='muted' style='font-size:.85rem;'>Top landing spots: {spots}</span>"))
                if spots else ui.div(),
            )

    # Stats section
    stats_df = dataio.player_stats()
    stats_section = ui.div()
    if len(stats_df):
        pid = r.get("player_id")
        s_row = stats_df[stats_df["player_id"] == pid] if pid else pd.DataFrame()
        if not s_row.empty:
            sr = s_row.iloc[0]
            stat_type = str(sr.get("stat_type", "")).upper()
            if stat_type == "BATTER":
                cards = [
                    ("AVG", sr.get("avg")), ("OBP", sr.get("obp")), ("SLG", sr.get("slg")),
                    ("OPS", sr.get("ops")), ("HR", sr.get("hr")), ("RBI", sr.get("rbi")), ("SB", sr.get("sb")),
                ]
            else:
                cards = [
                    ("ERA", sr.get("era")), ("WHIP", sr.get("whip")), ("K/9", sr.get("k_9")),
                    ("BB/9", sr.get("bb_9")), ("IP", sr.get("ip")), ("W", sr.get("w")), ("SV", sr.get("sv")),
                ]
            stat_html = "".join(
                f'<div class="stat-card"><div class="stat-value">{v if v is not None else "—"}</div>'
                f'<div class="stat-label">{lbl}</div></div>'
                for lbl, v in cards if v is not None
            )
            stats_section = ui.div(
                ui.hr(),
                ui.h4(f"2025 Stats ({stat_type})", style="font-size:.95rem;margin-bottom:.5rem;"),
                ui.HTML(f'<div class="stat-row">{stat_html}</div>'),
            )

    subtitle_parts = [str(r.get("class_level", "")), str(r.get("state", ""))]
    subtitle = " · ".join(p for p in subtitle_parts if p and p != "nan")

    return ui.modal(
        ui.div(
            ui.div(
                ui.span(f"Consensus #{int(r['consensus_rank'])}", class_="big-chip"),
                ui.span(f"avg {float(r['avg_rank']):.1f}", class_="src-chip"),
                ui.span(f"range {int(r['best_rank'])}–{int(r['worst_rank'])}", class_="src-chip"),
                ui.span(f"volatility {float(r['stdev']):.1f}", class_="src-chip"),
                ui.span(f"{int(r['n_sources'])} boards", class_="src-chip"),
                style="margin-bottom:.7rem;",
            ),
            ui.p(subtitle, class_="muted") if subtitle else ui.div(),
            ui.p(str(r.get("notes", "")), class_="muted") if r.get("notes") and str(r.get("notes")) != "nan" else ui.div(),
            ui.hr(),
            ui.h4("Board Rankings", style="font-size:.95rem;margin-bottom:.5rem;"),
            ui.div(*chips, class_="chip-row"),
            proj_section,
            stats_section,
            ui.hr(),
            _br_link(str(r["player"])),
            class_="detail-card",
            style="border:none;padding:0;margin:0;",
        ),
        title=f"{r['player']}  ·  {r['position']}  ·  {r['school']}",
        easy_close=True,
        size="l",
    )
