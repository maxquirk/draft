"""Tab 2 — Rankings Comparison: consensus vs every board, disagreement."""
from __future__ import annotations

import pandas as pd
from shiny import module, reactive, render, ui

from logic import dataio
from modules.player_modal import player_modal

_DF = dataio.consensus()
_KEYS = dataio.source_keys()


def _cell(src_rank, consensus_rank) -> str:
    if src_rank is None or (isinstance(src_rank, float) and pd.isna(src_rank)):
        return '<td class="bb-na">·</td>'
    src_rank = int(src_rank)
    diff = consensus_rank - src_rank
    cls = "bb-hi" if diff >= 15 else ("bb-lo" if diff <= -15 else "")
    return f'<td class="{cls}">{src_rank}</td>'


@module.ui
def bigboard_ui():
    return ui.div(
        ui.input_slider("topn", "Players to show (by consensus rank)", 10,
                        max(len(_DF), 20), min(40, max(len(_DF), 20))),
        ui.help_text("Green = this board is notably higher on the player than consensus; "
                     "red = notably lower. '·' = not ranked by that board."),
        ui.output_ui("matrix"),
        ui.h3("Biggest disagreements"),
        ui.help_text("Players the boards most disagree on — standard deviation of rank across boards."),
        ui.output_data_frame("disagree"),
        ui.output_ui("modal_host"),
    )


@module.server
def bigboard_server(input, output, session):
    input_id = session.ns("select_player")

    @render.ui
    def matrix():
        if not len(_DF):
            return ui.p("No data available.", class_="muted")
        d = _DF.nsmallest(input.topn(), "consensus_rank")
        head = "".join(
            f'<th class="bb-src">{dataio.source_label(k)}</th>' for k in _KEYS
        )
        body = []
        for _, r in d.iterrows():
            cr = int(r["consensus_rank"])
            cells = "".join(_cell(r.get(f"src_{k}"), cr) for k in _KEYS)
            safe_name = str(r["player"]).replace("'", "\\'").replace('"', '\\"')
            body.append(
                f'<tr><td class="bb-rank">{cr}</td>'
                f'<td class="bb-name" style="cursor:pointer" '
                f'onclick="Shiny.setInputValue(\'{input_id}\', \'{safe_name}\', {{priority:\'event\'}});">'
                f'{r["player"]}</td>'
                f'<td class="bb-pos">{r["position"]}</td>{cells}'
                f'<td class="bb-sd">{float(r["stdev"]):.1f}</td></tr>'
            )
        return ui.HTML(
            '<div class="bb-wrap"><table class="bb-table"><thead><tr>'
            '<th>Rank</th><th>Player</th><th>Pos</th>' + head +
            '<th>SD</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>"
        )

    @render.data_frame
    def disagree():
        if not len(_DF):
            return render.DataGrid(pd.DataFrame())
        d = _DF[_DF["n_sources"] >= 2].nlargest(40, "stdev")
        cols = ["consensus_rank", "player", "position", "school",
                "best_rank", "worst_rank", "spread", "stdev", "n_sources"]
        return render.DataGrid(d[cols], selection_mode="row", height="420px", width="100%")

    @render.ui
    def modal_host():
        # Name click from matrix table
        try:
            name = input.select_player()
            if name:
                ui.modal_show(player_modal(name))
                return ui.div()
        except Exception:
            pass
        # Row selection from disagree grid
        sel = disagree.data_view(selected=True)
        if sel is None or not len(sel):
            return ui.div()
        ui.modal_show(player_modal(sel.iloc[0]["player"]))
        return ui.div()
