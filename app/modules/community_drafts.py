"""Community Drafts tab — lists saved mock drafts from the repo CSV."""
from __future__ import annotations

import json

from shiny import module, reactive, render, ui


@module.ui
def community_drafts_ui():
    return ui.div(
        ui.div(
            ui.h3("Community Mock Drafts"),
            ui.p(
                "Saved drafts from everyone who used the Simulator. "
                "Refresh to see the latest.",
                class_="muted",
            ),
            ui.input_action_button("refresh", "Refresh", class_="btn-sm"),
            style="display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap;margin-bottom:.5rem;",
        ),
        ui.output_ui("draft_list"),
        ui.output_ui("draft_detail"),
    )


@module.server
def community_drafts_server(input, output, session):
    drafts = reactive.value([])
    selected_idx = reactive.value(None)
    load_counter = reactive.value(0)
    load_error = reactive.value("")

    @reactive.effect
    @reactive.event(input.refresh, ignore_none=False)
    async def _load():
        from logic.github_storage import load_drafts
        load_error.set("")
        load_counter.set(load_counter() + 1)
        try:
            result = await load_drafts()
            drafts.set(list(reversed(result)))  # newest first
        except Exception as e:
            load_error.set(str(e))
            drafts.set([])

    @render.ui
    def draft_list():
        if load_counter() == 0:
            return ui.p("Click Refresh to load community drafts.", class_="muted")
        err = load_error()
        if err:
            return ui.p(f"Error loading drafts: {err}", style="color:var(--bad);")
        rows = drafts()
        if not rows:
            return ui.p("No saved drafts yet — be the first!", class_="muted")

        options = {}
        for i, d in enumerate(rows):
            try:
                n_picks = len(json.loads(d.get("picks_json", "[]")))
            except Exception:
                n_picks = 0
            label = (
                f"{d.get('draft_name', 'Untitled')}  ·  "
                f"{d.get('author', '?')}  ·  "
                f"{d.get('saved_at', '')}  ·  "
                f"mode: {d.get('mode', '')}  ·  "
                f"{n_picks} picks"
            )
            options[str(i)] = label

        return ui.div(
            ui.input_select(
                "pick_draft",
                "Select a draft to view",
                choices={"": "— select a draft —", **options},
                selected="",
            ),
        )

    @reactive.effect
    @reactive.event(input.pick_draft)
    def _on_select():
        val = input.pick_draft()
        if val and val != "":
            try:
                selected_idx.set(int(val))
            except Exception:
                selected_idx.set(None)
        else:
            selected_idx.set(None)

    @render.ui
    def draft_detail():
        idx = selected_idx()
        rows = drafts()
        if idx is None or not rows or idx >= len(rows):
            return ui.div()
        d = rows[idx]
        try:
            picks = json.loads(d.get("picks_json", "[]"))
        except Exception:
            return ui.p("Could not parse this draft.", class_="muted")
        if not picks:
            return ui.p("No picks in this draft.", class_="muted")

        pick_rows = "".join(
            f"<tr>"
            f"<td class='bb-rank'>{p.get('pick', '')}</td>"
            f"<td>{p.get('team', '')}</td>"
            f"<td style='text-align:left;font-weight:600'>{p.get('player', '')}</td>"
            f"<td class='bb-pos'>{p.get('position', '')}</td>"
            f"<td style='text-align:left'>{p.get('school', '')}</td>"
            f"<td>{p.get('consensus_rank', '')}</td>"
            f"</tr>"
            for p in picks
        )
        return ui.div(
            ui.hr(),
            ui.h4(
                f"{d.get('draft_name', 'Untitled')}  ·  {d.get('author', '?')}",
                style="font-size:1rem;margin-bottom:.3rem;",
            ),
            ui.p(
                f"Mode: {d.get('mode', '')}  ·  Seed: {d.get('seed', '')}  ·  {d.get('saved_at', '')}",
                class_="muted",
            ),
            ui.HTML(
                "<div class='sim-wrap'><table class='sim-table'><thead><tr>"
                "<th>Pick</th><th>Team</th><th>Player</th><th>Pos</th>"
                "<th>School</th><th>Cons.</th>"
                "</tr></thead><tbody>" + pick_rows + "</tbody></table></div>"
            ),
            class_="detail-card",
        )
