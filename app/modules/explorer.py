"""Tab — Player Search: search-first with recent players."""
from __future__ import annotations

import pandas as pd
from shiny import module, reactive, render, ui

from logic import dataio
from modules.player_modal import player_modal

_DF = dataio.consensus()


def _player_card(name: str, rank: int, pos: str, school: str, input_id: str) -> ui.Tag:
    safe_name = name.replace("'", "\\'").replace('"', '\\"')
    return ui.div(
        ui.div(
            ui.span(f"#{rank}", class_="src-chip"),
            ui.strong(name),
            ui.span(f" · {pos}", class_="muted"),
        ),
        ui.div(school, class_="muted", style="font-size:.83rem;"),
        class_="player-card",
        style="cursor:pointer;",
        onclick=f"Shiny.setInputValue('{input_id}', '{safe_name}', {{priority:'event'}});",
    )


@module.ui
def explorer_ui():
    return ui.div(
        ui.div(
            ui.input_text("q", None, placeholder="Search by name or school…", width="100%"),
            style="max-width:460px;margin-bottom:1.2rem;",
        ),
        ui.output_ui("results"),
        ui.output_ui("modal_host"),
    )


@module.server
def explorer_server(input, output, session):
    recent: reactive.Value[list[str]] = reactive.Value([])
    input_id = session.ns("select_player")

    @reactive.calc
    def matches() -> list[dict]:
        q = (input.q() or "").strip().lower()
        if len(q) < 2:
            return []
        mask = (
            _DF["player"].str.lower().str.contains(q, na=False)
            | _DF["school"].str.lower().str.contains(q, na=False)
        )
        return _DF[mask].nsmallest(20, "consensus_rank")[
            ["player", "consensus_rank", "position", "school"]
        ].to_dict("records")

    @render.ui
    def results():
        q = (input.q() or "").strip()

        if len(q) >= 2:
            hits = matches()
            if not hits:
                return ui.p("No players found.", class_="muted")
            return ui.div(
                *[_player_card(r["player"], int(r["consensus_rank"]),
                               str(r["position"]), str(r["school"]), input_id)
                  for r in hits],
                class_="player-card-grid",
            )

        rec = recent.get()
        if not rec:
            return ui.p("Search for a player above to see their scouting profile.", class_="muted")

        rows = []
        for name in rec:
            row = _DF[_DF["player"] == name]
            if not row.empty:
                r = row.iloc[0]
                rows.append(_player_card(
                    name, int(r["consensus_rank"]), str(r["position"]), str(r["school"]), input_id,
                ))

        return ui.div(
            ui.p("Recent", class_="muted",
                 style="font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;margin-bottom:.6rem;"),
            ui.div(*rows, class_="player-card-grid"),
        )

    @render.ui
    def modal_host():
        try:
            name = input.select_player()
        except Exception:
            return ui.div()
        if not name:
            return ui.div()

        rec = [n for n in recent.get() if n != name]
        recent.set([name] + rec[:7])

        ui.modal_show(player_modal(name))
        return ui.div()
