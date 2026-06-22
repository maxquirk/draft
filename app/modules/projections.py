"""Tab — Draft Projections: Monte Carlo expected outcome per player.

Aggregates many simulated drafts (consensus board x real 2026 order x team
tendencies) into each player's projected slot, landing team, and round-1 odds.
Uses the same render.data_frame grid the Explorer uses (renders reliably in
shinylive/Pyodide).
"""
from __future__ import annotations

import pandas as pd
from shiny import module, reactive, render, ui

from logic import dataio

_DF = dataio.projections()
_META = dataio.projections_meta()
_TEAMS = sorted(_DF["likely_team"].dropna().unique()) if len(_DF) else []
_MAXPICK = int(_DF["proj_pick"].max()) if len(_DF) else 40

_DISPLAY = ["proj_pick", "player", "position", "school", "consensus_rank",
            "range", "round1_pct", "landing"]
_RENAME = {"proj_pick": "Proj", "player": "Player", "position": "Pos",
           "school": "School", "consensus_rank": "Consensus", "range": "Pick range",
           "round1_pct": "Round-1 %", "landing": "Likely landing (freq)"}


@module.ui
def projections_ui():
    if not len(_DF):
        return ui.p("No projections yet — run the scraper (it runs the Monte Carlo "
                    "after building the board and team data).", class_="muted")
    return ui.layout_sidebar(
        ui.sidebar(
            ui.input_slider("maxpick", "Show players projected within pick",
                            5, max(_MAXPICK, 6), min(_MAXPICK, _MAXPICK)),
            ui.input_selectize("team", "Likely landing team", ["(all)"] + _TEAMS),
            ui.help_text("Round-1 % = share of simulations the player was taken in "
                         "the first round. Pick range = 10th–90th-percentile pick."),
            width=340,
        ),
        ui.p(_META.get("note", ""), class_="muted"),
        ui.output_data_frame("grid"),
    )


@module.server
def projections_server(input, output, session):
    @reactive.calc
    def filtered() -> pd.DataFrame:
        d = _DF[_DF["proj_pick"] <= input.maxpick()]
        if input.team() and input.team() != "(all)":
            d = d[d["likely_team"] == input.team()]
        return d

    @render.data_frame
    def grid():
        d = filtered().copy()
        if not len(d):
            return render.DataGrid(pd.DataFrame({"info": ["No players match."]}))
        d["range"] = (d["proj_low"].astype(int).astype(str) + "–"
                      + d["proj_high"].astype(int).astype(str))
        d["round1_pct"] = (d["p_round1"] * 100).round().astype(int).astype(str) + "%"
        d["landing"] = (d["likely_team"] + " ("
                        + (d["likely_team_pct"] * 100).round().astype(int).astype(str)
                        + "%)")
        out = d[_DISPLAY].rename(columns=_RENAME)
        return render.DataGrid(out, height="600px", width="100%")
