"""Tab — Draft Projections: Monte Carlo expected outcome per player.

Built with the SAME structure that renders reliably in shinylive/Pyodide on the
Mock Simulator tab: a top-level layout_sidebar (not wrapped in a div) whose main
area is a render.ui returning an ui.HTML table.
"""
from __future__ import annotations

from shiny import module, reactive, render, ui

from logic import dataio

_DF = dataio.projections()
_META = dataio.projections_meta()
_TEAMS = sorted(_DF["likely_team"].dropna().unique()) if len(_DF) else []
_MAXPICK = int(_DF["proj_pick"].max()) if len(_DF) else 40


@module.ui
def projections_ui():
    if not len(_DF):
        return ui.p("No projections yet — run the scraper (it runs the Monte Carlo "
                    "after building the board and team data).", class_="muted")
    return ui.layout_sidebar(
        ui.sidebar(
            ui.input_slider("maxpick", "Show players projected within pick",
                            5, max(_MAXPICK, 6), _MAXPICK),
            ui.input_selectize("team", "Likely landing team", ["(all)"] + _TEAMS),
            ui.help_text("Round-1 % = share of simulations the player was taken in "
                         "round 1. Range = 10th–90th-percentile pick across sims."),
            width=340,
        ),
        ui.output_ui("table"),
    )


@module.server
def projections_server(input, output, session):
    @reactive.calc
    def filtered():
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
            pr1 = int(round(100 * float(r["p_round1"])))
            pct = int(round(100 * float(r["likely_team_pct"])))
            rows.append(
                "<tr>"
                f"<td>{int(r['proj_pick'])}</td>"
                f"<td style='text-align:left;font-weight:600'>{r['player']}</td>"
                f"<td>{r['position']}</td>"
                f"<td style='text-align:left'>{r['school']}</td>"
                f"<td>{int(r['consensus_rank'])}</td>"
                f"<td>{int(r['proj_low'])}-{int(r['proj_high'])}</td>"
                f"<td>{r['likely_team']} <span class='muted'>({pct}%)</span></td>"
                f"<td>{pr1}%</td>"
                "</tr>"
            )
        note = f"<p class='muted'>{_META.get('note', '')}</p>"
        return ui.HTML(
            note + "<div class='sim-wrap'><table class='sim-table'><thead><tr>"
            "<th>Proj.</th><th>Player</th><th>Pos</th><th>School</th><th>Cons.</th>"
            "<th>Range</th><th>Likely landing</th><th>Round-1 %</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        )
