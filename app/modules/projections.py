"""Tab — Draft Projections: Monte Carlo expected outcome per player.

Aggregates many simulated drafts (consensus board x real 2026 order x team
tendencies) into each player's projected slot, landing team, and round-1 odds.
"""
from __future__ import annotations

import pandas as pd
from shiny import module, reactive, render, ui

from logic import dataio

_DF = dataio.projections()
_META = dataio.projections_meta()
_TEAMS = sorted(_DF["likely_team"].dropna().unique()) if len(_DF) else []


@module.ui
def projections_ui():
    if not len(_DF):
        return ui.p("No projections yet — run the scraper (it runs the Monte Carlo "
                    "after building the board and team data).", class_="muted")
    return ui.div(
        ui.p(_META.get("note", ""), class_="muted"),
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_slider("maxpick", "Show players projected within pick", 5,
                                int(_DF["proj_pick"].max()), min(40, int(_DF["proj_pick"].max()))),
                ui.input_selectize("team", "Likely landing team", ["(all)"] + _TEAMS),
                ui.help_text("R1% = share of simulations the player was taken in round 1. "
                             "Range = 10th–90th-percentile pick across sims."),
                width=320,
            ),
            ui.output_ui("table"),
        ),
    )


@module.server
def projections_server(input, output, session):
    @reactive.calc
    def filtered() -> pd.DataFrame:
        d = _DF[_DF["proj_pick"] <= input.maxpick()]
        if input.team() and input.team() != "(all)":
            d = d[d["likely_team"] == input.team()]
        return d

    @render.ui
    def table():
        d = filtered()
        if not len(d):
            return ui.p("No players match.", class_="muted")
        rows = []
        for _, r in d.iterrows():
            pr1 = int(round(100 * r["p_round1"]))
            bar = (f'<span class="p1-track"><span class="p1-fill" '
                   f'style="width:{pr1}%"></span></span>')
            rows.append(
                f'<tr><td class="pj-pick">{int(r["proj_pick"])}</td>'
                f'<td class="pj-name">{r["player"]}</td><td>{r["position"]}</td>'
                f'<td>{r["school"]}</td><td>{int(r["consensus_rank"])}</td>'
                f'<td>{int(r["proj_low"])}–{int(r["proj_high"])}</td>'
                f'<td>{r["likely_team"]} '
                f'<span class="muted">({int(round(100*r["likely_team_pct"]))}%)</span></td>'
                f'<td>{bar}<span class="p1-num">{pr1}%</span></td></tr>'
            )
        return ui.HTML(
            '<div class="sim-wrap"><table class="sim-table"><thead><tr>'
            '<th>Proj.</th><th>Player</th><th>Pos</th><th>School</th><th>Cons.</th>'
            '<th>Range</th><th>Likely landing</th><th>Round-1 odds</th>'
            '</tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
        )
