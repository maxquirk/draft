"""Tab 1 — Prospect Explorer: searchable / filterable board with player modal."""
from __future__ import annotations

import pandas as pd
from shiny import module, reactive, render, ui

from logic import dataio
from modules.player_modal import player_modal

_DF = dataio.consensus()
_STATS = dataio.player_stats()
_SRC_KEYS = dataio.source_keys()
_POS = sorted([p for p in _DF["position"].dropna().unique() if p]) if len(_DF) else []
_CLS = sorted([c for c in _DF["class_level"].dropna().unique() if c and str(c) != "nan"]) if len(_DF) else []
_MAXR = int(_DF["consensus_rank"].max()) if len(_DF) else 1
_MAXS = int(_DF["n_sources"].max()) if len(_DF) else 1

# Per-source rank columns (e.g. "MLB Pipeline", "FanGraphs", ...)
_SRC_COLS = [f"src_{k}" for k in _SRC_KEYS]
_SRC_LABELS = {f"src_{k}": dataio.source_label(k) for k in _SRC_KEYS}

# Base columns always shown
_BASE_COLS = ["consensus_rank", "player", "position", "school", "class_level"] + _SRC_COLS

# Stat columns for college players
_BATTER_STATS = ["avg", "obp", "slg", "ops", "hr", "rbi", "sb"]
_PITCHER_STATS = ["era", "whip", "k_9", "bb_9", "ip"]


def _build_display(df: pd.DataFrame) -> pd.DataFrame:
    """Build the display frame: base columns + per-source ranks.
    For college players with stats, merge those in."""
    out = df[_BASE_COLS].copy()
    # Rename src_* columns to readable source names
    out = out.rename(columns=_SRC_LABELS)
    # Merge stats for college players
    if len(_STATS):
        merged = out.merge(
            _STATS[["player_id", "stat_type", "avg", "obp", "slg", "ops",
                    "hr", "rbi", "sb", "era", "whip", "k_9", "bb_9", "ip"]],
            left_on="player_id" if "player_id" in out.columns else None,
            right_on="player_id",
            how="left",
        ) if "player_id" in df.columns else out
        return merged if len(merged) == len(out) else out
    return out


@module.ui
def explorer_ui():
    return ui.layout_sidebar(
        ui.sidebar(
            ui.input_text("q", "Search player / school"),
            ui.input_selectize("pos", "Position", choices=_POS, multiple=True),
            ui.input_selectize("cls", "Class", choices=_CLS, multiple=True),
            ui.input_slider("min_sources", "Min boards", 1, max(_MAXS, 2), 1),
            ui.input_slider("max_rank", "Max rank", 1, max(_MAXR, 2), max(_MAXR, 2)),
            ui.help_text("Click a player row to open their profile."),
            width=280,
        ),
        ui.output_ui("count"),
        ui.output_data_frame("grid"),
        ui.output_ui("modal_host"),
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
        return ui.p(ui.strong(f"{n}"), " players shown", class_="muted")

    @render.data_frame
    def grid():
        d = filtered()
        if not len(d):
            return render.DataGrid(d, selection_mode="row", height="520px", width="100%")
        display = _build_display(d)
        return render.DataGrid(display, selection_mode="row", height="520px", width="100%")

    @render.ui
    def modal_host():
        sel = grid.data_view(selected=True)
        if sel is None or not len(sel):
            return ui.div()
        name = sel.iloc[0]["player"]
        m = player_modal(name)
        ui.modal_show(m)
        return ui.div()
