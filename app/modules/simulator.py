"""Tab 3 -- Mock-Draft Simulator. Auto-sim or go on-the-clock for one team."""
from __future__ import annotations

import io

import pandas as pd
from shiny import module, reactive, render, ui

from logic import dataio, github_storage
from logic.sim_engine import simulate

# First-round mock: only the top 50 consensus players are in the draftable pool.
_BOARD = (dataio.consensus().sort_values("consensus_rank").head(50).to_dict("records")
          if len(dataio.consensus()) else [])
_ORDER = dataio.draft_order()
_TEND = dataio.team_tendencies()
_TEAMS = [s.get("team", "") for s in _ORDER]
_BY_ID = {p["player_id"]: p for p in _BOARD}


def _choice_label(p: dict) -> str:
    return f"#{int(p['consensus_rank'])}  {p['player']} ({p.get('position','')}, {p.get('school','')})"


@module.ui
def simulator_ui():
    if not _BOARD or not _ORDER:
        return ui.p("Simulator needs both a consensus board and a 2026 draft order -- "
                    "run the scraper first.", class_="muted")
    return ui.layout_sidebar(
        ui.sidebar(
            ui.input_select("mode", "Engine", {
                "realistic": "Realistic (team lean + noise)",
                "team_need": "Team need (no noise)",
                "bpa": "Best player available",
            }, selected="realistic"),
            ui.input_slider("rand", "Unpredictability", 0.0, 0.4, 0.15, step=0.05),
            ui.input_numeric("seed", "Random seed", 1, min=1, max=99999),
            ui.hr(),
            ui.input_select("team", "Go on the clock as", ["(spectate -- auto only)"] + _TEAMS),
            ui.input_action_button("reset", "Reset draft", class_="btn-sm"),
            ui.download_button("dl", "Download CSV", class_="btn-sm"),
            ui.hr(),
            ui.input_action_button("save_btn", "Save Draft", class_="btn-sm"),
            width=320,
        ),
        ui.output_ui("clock"),
        ui.output_ui("pick_panel"),
        ui.output_ui("results"),
    )


@module.server
def simulator_server(input, output, session):
    committed = reactive.value({})  # pick_no -> player_id (user + finalized CPU)
    save_status = reactive.value("")

    @reactive.effect
    @reactive.event(input.reset, input.mode, input.rand, input.seed)
    def _reset():
        committed.set({})

    @reactive.calc
    def projection() -> list[dict]:
        """Full projected draft given current committed picks."""
        if not _BOARD or not _ORDER:
            return []
        return simulate(_BOARD, _ORDER, _TEND, mode=input.mode(),
                        randomness=input.rand(), seed=int(input.seed() or 1),
                        locked=committed())

    def _on_clock_idx() -> int | None:
        c = committed()
        for i, slot in enumerate(_ORDER):
            if slot.get("pick") not in c:
                return i
        return None

    @render.ui
    def clock():
        idx = _on_clock_idx()
        if idx is None:
            return ui.div(ui.h3("Draft complete"), class_="clock-done")
        slot = _ORDER[idx]
        my_team = input.team()
        on_user = my_team in _TEAMS and slot.get("team") == my_team

        head = ui.h3(f"Pick {slot.get('pick')} -- {slot.get('team')} "
                     f"{'(you)' if on_user else 'on the clock'}")
        if on_user:
            return ui.div(
                head,
                ui.input_text("pick_search", None,
                              placeholder="Search players by name, school, or position…",
                              width="100%"),
                ui.output_text_verbatim("pick_selection", placeholder=True),
                ui.input_action_button("draft", "Draft selected", class_="btn-primary"),
                class_="clock-box",
            )
        return ui.div(
            head,
            ui.input_action_button("advance", "Auto-pick this one", class_="btn-sm"),
            ui.input_action_button("tonext", "Sim to my next pick", class_="btn-sm"),
            ui.input_action_button("auto", "Auto-complete draft", class_="btn-primary"),
            class_="clock-box",
        )

    # -- Player search for on-clock picks -----------------------------------

    selected_pid: reactive.Value[str] = reactive.Value("")
    input_id = session.ns("pickfor")

    @reactive.calc
    def _avail() -> list[dict]:
        taken = set(committed().values())
        return [p for p in _BOARD if p["player_id"] not in taken]

    @render.ui
    def pick_panel():
        idx = _on_clock_idx()
        if idx is None:
            return ui.div()
        slot = _ORDER[idx]
        my_team = input.team()
        if not (my_team in _TEAMS and slot.get("team") == my_team):
            return ui.div()
        q = (input.pick_search() or "").strip().lower()
        avail = _avail()
        if q:
            avail = [p for p in avail
                     if q in p["player"].lower()
                     or q in p.get("school", "").lower()
                     or q in p.get("position", "").lower()][:20]
        else:
            avail = avail[:20]
        sel = selected_pid()
        rows = []
        for p in avail:
            pid = p["player_id"]
            is_sel = pid == sel
            safe_pid = pid.replace("'", "\\'")
            style = ("background:var(--accent-bg);border-color:var(--accent);"
                     if is_sel else "")
            rows.append(
                f"<div class='sim-pick-row' style='{style}' "
                f"onclick=\"Shiny.setInputValue('{input_id}', '{safe_pid}', {{priority:'event'}});\">"
                f"<span class='bb-rank'>#{int(p['consensus_rank'])}</span> "
                f"<strong>{p['player']}</strong> "
                f"<span class='bb-pos'>{p.get('position','')} · {p.get('school','')}</span>"
                f"</div>"
            )
        if not rows:
            return ui.div(ui.p("No players found.", class_="muted"),
                          style="margin-top:.5rem;")
        return ui.div(
            ui.HTML("<div class='sim-pick-list'>" + "".join(rows) + "</div>"),
            style="margin-top:.5rem;",
        )

    @reactive.effect
    @reactive.event(input.pickfor)
    def _on_pick_select():
        pid = input.pickfor()
        if pid:
            selected_pid.set(pid)

    @render.text
    def pick_selection():
        pid = selected_pid()
        if not pid:
            return "No player selected"
        p = next((x for x in _BOARD if x["player_id"] == pid), None)
        if not p:
            return "No player selected"
        return f"Selected: #{int(p['consensus_rank'])} {p['player']} ({p.get('position','')})"

    @reactive.effect
    @reactive.event(input.draft)
    def _draft():
        idx = _on_clock_idx()
        if idx is None:
            return
        pid = selected_pid()
        if not pid:
            return
        c = dict(committed())
        c[_ORDER[idx].get("pick")] = pid
        selected_pid.set("")
        committed.set(c)

    @reactive.effect
    @reactive.event(input.advance)
    def _advance():
        _commit_cpu_until(stop_at_user=False, one=True)

    @reactive.effect
    @reactive.event(input.tonext)
    def _tonext():
        _commit_cpu_until(stop_at_user=True, one=False)

    @reactive.effect
    @reactive.event(input.auto)
    def _auto():
        proj = {r["pick"]: r["player_id"] for r in projection()}
        committed.set(proj)

    def _commit_cpu_until(*, stop_at_user: bool, one: bool):
        proj = {r["pick"]: r["player_id"] for r in projection()}
        c = dict(committed())
        my_team = input.team()
        for slot in _ORDER:
            pk = slot.get("pick")
            if pk in c:
                continue
            if slot.get("team") == my_team and my_team in _TEAMS:
                break  # reached the user's pick
            c[pk] = proj.get(pk)
            if one:
                break
            if not stop_at_user:
                break
        committed.set(c)

    @render.ui
    def results():
        proj = projection()
        if not proj:
            return ui.div()
        my_team = input.team()
        rows = []
        cset = committed()
        for r in proj:
            done = r["pick"] in cset
            tag = ("you" if r["team"] == my_team and my_team in _TEAMS else "")
            cls = " sim-you" if tag else ""
            cls += " sim-locked" if done else " sim-proj"
            val = r["value"]
            # val = consensus_rank - pick; negative = value (player fell), positive = reach
            vtxt = (f'<span class="val-neg">+{val}</span>' if isinstance(val, (int, float)) and val > 0
                    else (f'<span class="val-pos">{val}</span>' if isinstance(val, (int, float)) and val < 0 else ""))
            rows.append(
                f'<tr class="{cls}"><td>{r["pick"]}</td><td>{r["team"]}</td>'
                f'<td>{r["player"]}</td><td>{r["position"]}</td>'
                f'<td>{r["school"]}</td><td>{r["consensus_rank"]}</td><td>{vtxt}</td></tr>'
            )
        return ui.div(
            ui.help_text("Solid rows are finalized; faded rows are projected. "
                         "Green = value (player fell); Red = reach (taken early)."),
            ui.HTML('<div class="sim-wrap"><table class="sim-table"><thead><tr>'
                    '<th>Pick</th><th>Team</th><th>Player</th><th>Pos</th><th>School</th>'
                    '<th>Cons.</th><th>Value</th></tr></thead><tbody>'
                    + "".join(rows) + "</tbody></table></div>"),
        )

    # -- Save Draft ----------------------------------------------------------

    @reactive.effect
    @reactive.event(input.save_btn)
    def _show_save_modal():
        save_status.set("")
        m = ui.modal(
            ui.input_text("draft_name", "Draft name", placeholder="My Mock Draft"),
            ui.input_text("draft_author", "Your name", placeholder="Your name"),
            ui.output_ui("save_msg"),
            title="Save Mock Draft",
            easy_close=True,
            footer=ui.div(
                ui.input_action_button("save_confirm", "Save", class_="btn-primary"),
                ui.modal_button("Cancel"),
            ),
        )
        ui.modal_show(m)

    @render.ui
    def save_msg():
        msg = save_status()
        if not msg:
            return ui.div()
        color = "var(--good)" if "saved" in msg.lower() else "var(--bad)"
        return ui.p(msg, style=f"color:{color};margin-top:.5rem;")

    @reactive.effect
    @reactive.event(input.save_confirm)
    async def _do_save():
        picks = projection()
        if not picks:
            save_status.set("No picks to save -- run the draft first.")
            return
        save_status.set("Saving...")
        safe_keys = ("pick", "team", "player", "position", "school", "consensus_rank")
        clean_picks = [{k: r[k] for k in safe_keys if k in r} for r in picks]
        ok, msg = await github_storage.save_draft(
            draft_name=input.draft_name(),
            author=input.draft_author(),
            mode=input.mode(),
            seed=int(input.seed() or 1),
            picks=clean_picks,
        )
        save_status.set(msg)
        if ok:
            ui.modal_remove()

    # -- Download ------------------------------------------------------------

    @render.download(filename="mock_draft_2026.csv")
    def dl():
        proj = projection()
        if proj:
            buf = io.StringIO()
            pd.DataFrame(proj)[["pick", "team", "player", "position", "school",
                                "consensus_rank", "value"]].to_csv(buf, index=False)
            yield buf.getvalue()
