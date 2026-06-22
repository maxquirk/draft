"""Tab 1 — Prospect Explorer: searchable / filterable board with a detail card."""
from __future__ import annotations

import pandas as pd
from shiny import module, reactive, render, ui

from logic import dataio

_DF = dataio.consensus()
_POS = sorted([p for p in _DF["position"].dropna().unique() if p]) if len(_DF) else []
_CLS = sorted([c for c in _DF["class_level"].dropna().unique() if c]) if len(_DF) else []
_MAXR = int(_DF["consensus_rank"].max()) if len(_DF) else 1
_MAXS = int(_DF["n_sources"].max()) if len(_DF) else 1

_GRID_COLS = ["consensus_rank", "player", "position", "school", "class_level",
              "n_sources", "avg_rank", "best_rank", "worst_rank", "stdev"]


@module.ui
def explorer_ui():
    return ui.layout_sidebar(
        ui.sidebar(
            ui.input_text("q", "Search player / school"),
            ui.input_selectize("pos", "Position", choices=_POS, multiple=True),
            ui.input_selectize("cls", "Class", choices=_CLS, multiple=True),
            ui.input_slider("min_sources", "Min # of boards ranking the player",
                            1, max(_MAXS, 2), 1),
            ui.input_slider("max_rank", "Max consensus rank", 1, max(_MAXR, 2), max(_MAXR, 2)),
            ui.help_text("Click a row to see every board's rank for that player."),
            width=320,
        ),
        ui.output_ui("count"),
        ui.output_data_frame("grid"),
        ui.output_ui("detail"),
    )


@module.server
def explorer_server(input, output, session):
    @reactive.calc
    def filtered() -> pd.DataFrame:
        d = _DF
        if not len(d):
            return d
        q = input.q().strip().lower()
        if q:
            d = d[d["player"].str.lower().str.contains(q, na=False)
                  | d["school"].str.lower().str.contains(q, na=False)]
        if input.pos():
            d = d[d["position"].isin(input.pos())]
        if input.cls():
            d = d[d["class_level"].isin(input.cls())]
        d = d[d["n_sources"] >= input.min_sources()]
        d = d[d["consensus_rank"] <= input.max_rank()]
        return d

    @render.ui
    def count():
        n = len(filtered())
        gen = dataio.report().get("generated_at", "never")
        return ui.p(ui.strong(f"{n}"), f" players shown · data generated {gen}",
                    class_="muted")

    @render.data_frame
    def grid():
        d = filtered()[_GRID_COLS] if len(filtered()) else filtered()
        return render.DataGrid(d, selection_mode="row", height="520px", width="100%")

    @render.ui
    def detail():
        sel = grid.data_view(selected=True)
        if sel is None or not len(sel):
            return ui.div()
        name = sel.iloc[0]["player"]
        row = _DF[_DF["player"] == name]
        if not len(row):
            return ui.div()
        r = row.iloc[0]
        ranks = r.get("rankings") or {}
        chips = [
            ui.span(f"{dataio.source_label(k)}: #{v}", class_="src-chip")
            for k, v in sorted(ranks.items(), key=lambda kv: kv[1])
        ]
        return ui.div(
            ui.h3(f"{r['player']}  ·  {r['position']}  ·  {r['school']}"),
            ui.p(f"{r.get('class_level','')} {('· ' + r['state']) if r.get('state') else ''}",
                 class_="muted"),
            ui.div(
                ui.span(f"Consensus #{int(r['consensus_rank'])}", class_="big-chip"),
                ui.span(f"avg {r['avg_rank']}", class_="src-chip"),
                ui.span(f"median {r['median_rank']}", class_="src-chip"),
                ui.span(f"range {int(r['best_rank'])}–{int(r['worst_rank'])}", class_="src-chip"),
                ui.span(f"volatility {r['stdev']}", class_="src-chip"),
                ui.span(f"{int(r['n_sources'])} boards", class_="src-chip"),
            ),
            ui.p(ui.strong("By board:")),
            ui.div(*chips, class_="chip-row"),
            ui.p(r.get("notes", ""), class_="muted") if r.get("notes") else None,
            class_="detail-card",
        )
