"""Tab — Draft Projections: Monte Carlo expected outcome per player.

Same render shape as the Mock Simulator tab (top-level layout_sidebar + a
render.ui ui.HTML table), which renders reliably in shinylive/Pyodide.
Each player's landing is the top-3 most likely ACTUAL-order pick slots.
"""
from __future__ import annotations

from shiny import module, reactive, render, ui

from logic import dataio

_DF = dataio.projections()
_META = dataio.projections_meta()


def _landing_list(v):
    return v if isinstance(v, list) else []


_TEAMS = sorted({l["team"] for v in (_DF["landing"] if "landing" in _DF else [])
                 for l in _landing_list(v) if l.get("team")}) if len(_DF) else []
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
            ui.input_selectize("team", "Lands with team", ["(all)"] + _TEAMS),
            ui.help_text("Round-1 % = share of simulations the player went in round 1. "
                         "Landing spots are the 3 most likely ACTUAL-order picks "
                         "(pick # → team) with how often the sims sent him there."),
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
            d = d[d["landing"].apply(
                lambda v: input.team() in [l["team"] for l in _landing_list(v)])]
        return d

    @render.ui
    def table():
        d = filtered()
        if not len(d):
            return ui.p("No players match.", class_="muted")
        rows = []
        for _, r in d.iterrows():
            pr1 = int(round(100 * float(r["p_round1"])))
            spots = " · ".join(
                f"<b>{l['pick']}</b> {l['team']} "
                f"<span class='muted'>{int(round(100 * l['pct']))}%</span>"
                for l in _landing_list(r["landing"])
            )
            rows.append(
                "<tr>"
                f"<td>{int(r['proj_pick'])}</td>"
                f"<td style='text-align:left;font-weight:600'>{r['player']}</td>"
                f"<td>{r['position']}</td>"
                f"<td style='text-align:left'>{r['school']}</td>"
                f"<td>{int(r['consensus_rank'])}</td>"
                f"<td>{int(r['proj_low'])}-{int(r['proj_high'])}</td>"
                f"<td>{pr1}%</td>"
                f"<td style='text-align:left'>{spots}</td>"
                "</tr>"
            )
        note = f"<p class='muted'>{_META.get('note', '')}</p>"
        return ui.HTML(
            note + "<div class='sim-wrap'><table class='sim-table'><thead><tr>"
            "<th>Proj.</th><th>Player</th><th>Pos</th><th>School</th><th>Cons.</th>"
            "<th>Range</th><th>Round-1 %</th><th>Top-3 likely landing spots (pick → team)</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        )
