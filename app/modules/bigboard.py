"""Tab 2 — Big-Board Comparison: consensus vs every source, disagreement & helium."""
from __future__ import annotations

import pandas as pd
from shiny import module, reactive, render, ui

from logic import dataio

_DF = dataio.consensus()
_KEYS = dataio.source_keys()


def _cell(src_rank, consensus_rank) -> str:
    if src_rank is None or (isinstance(src_rank, float) and pd.isna(src_rank)):
        return '<td class="bb-na">·</td>'
    src_rank = int(src_rank)
    diff = consensus_rank - src_rank  # +ve => this board is higher (more bullish)
    cls = "bb-hi" if diff >= 15 else ("bb-lo" if diff <= -15 else "")
    return f'<td class="{cls}">{src_rank}</td>'


@module.ui
def bigboard_ui():
    return ui.div(
        ui.input_slider("topn", "Players to compare (by consensus)", 10,
                        max(len(_DF), 20), min(40, max(len(_DF), 20))),
        ui.help_text("Green = this board is notably higher on the player than consensus; "
                     "red = notably lower. '·' = unranked by that board."),
        ui.output_ui("matrix"),
        ui.h3("Biggest disagreements (board volatility)"),
        ui.help_text("Players the boards most disagree on — standard deviation of rank across boards."),
        ui.output_data_frame("disagree"),
    )


@module.server
def bigboard_server(input, output, session):
    @render.ui
    def matrix():
        if not len(_DF):
            return ui.p("No data yet — run the scraper.", class_="muted")
        d = _DF.nsmallest(input.topn(), "consensus_rank")
        head = "".join(
            f'<th class="bb-src">{dataio.source_label(k)}</th>' for k in _KEYS
        )
        body = []
        for _, r in d.iterrows():
            cr = int(r["consensus_rank"])
            cells = "".join(_cell(r.get(f"src_{k}"), cr) for k in _KEYS)
            body.append(
                f'<tr><td class="bb-rank">{cr}</td>'
                f'<td class="bb-name">{r["player"]}</td>'
                f'<td class="bb-pos">{r["position"]}</td>{cells}'
                f'<td class="bb-sd">{r["stdev"]:g}</td></tr>'
            )
        return ui.HTML(
            '<div class="bb-wrap"><table class="bb-table"><thead><tr>'
            '<th>Cons.</th><th>Player</th><th>Pos</th>' + head +
            '<th>SD</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>"
        )

    @render.data_frame
    def disagree():
        if not len(_DF):
            return render.DataGrid(pd.DataFrame())
        d = _DF[_DF["n_sources"] >= 2].nlargest(40, "stdev")
        cols = ["consensus_rank", "player", "position", "school",
                "best_rank", "worst_rank", "spread", "stdev", "n_sources"]
        return render.DataGrid(d[cols], height="420px", width="100%")
