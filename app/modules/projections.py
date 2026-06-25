"""Tab — Draft Projections: Monte Carlo expected outcome per player."""
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
_ALL_ROUNDS = max(_MAXPICK, 40)


@module.ui
def projections_ui():
    if not len(_DF):
        return ui.p("No projections available yet.", class_="muted")
    return ui.layout_sidebar(
        ui.sidebar(
            ui.input_slider("maxpick", "Max projected pick",
                            5, max(_ALL_ROUNDS, 6), _ALL_ROUNDS),
            ui.input_selectize("team", "Filter by landing team", ["(all)"] + _TEAMS),
            ui.input_slider("min_r1", "Min round-1 probability (%)", 0, 100, 0),
            ui.help_text("Round-1 % = share of simulations the player went in round 1."),
            width=300,
        ),
        ui.output_ui("table"),
    )


@module.server
def projections_server(input, output, session):
    @reactive.calc
    def filtered():
        d = _DF[_DF["proj_pick"] <= input.maxpick()]
        min_r1 = input.min_r1() / 100.0
        if min_r1 > 0:
            d = d[d["p_round1"] >= min_r1]
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
                f"<b>#{l['pick']}</b> {l['team']} "
                f"<span class='muted'>{int(round(100 * l['pct']))}%</span>"
                for l in _landing_list(r.get("landing", []))
            )
            rows.append(
                "<tr>"
                f"<td class='pj-pick'>{int(r['proj_pick'])}</td>"
                f"<td class='pj-name'>{r['player']}</td>"
                f"<td>{r['position']}</td>"
                f"<td style='text-align:left'>{r['school']}</td>"
                f"<td>{int(r['consensus_rank'])}</td>"
                f"<td>{int(r['proj_low'])}-{int(r['proj_high'])}</td>"
                f"<td>"
                f"<span class='p1-track'><span class='p1-fill' style='width:{pr1}%'></span></span>"
                f"<span class='p1-num'>{pr1}%</span>"
                f"</td>"
                f"<td style='text-align:left;font-size:.82rem'>{spots}</td>"
                "</tr>"
            )
        runs = _META.get('runs', 0)
        note = f"<p class='muted' style='font-size:.8rem;'>{runs:,} simulations</p>" if runs else ""
        return ui.HTML(
            note + "<div class='sim-wrap'><table class='sim-table'><thead><tr>"
            "<th>Proj.</th><th>Player</th><th>Pos</th><th>School</th><th>Cons.</th>"
            "<th>Range</th><th>Round-1 %</th><th>Top landing spots</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        )
