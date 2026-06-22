"""Tab 4 — Team Strategy: how each club has historically targeted the draft."""
from __future__ import annotations

from shiny import module, render, ui

from logic import dataio
from logic.viz import bars, stat_card

_TEND = dataio.team_tendencies()
_HIST = dataio.team_history()
_TEAMS = sorted(_TEND.keys())


def _pct(x) -> str:
    try:
        return f"{100 * float(x):.0f}%"
    except (TypeError, ValueError):
        return "—"


@module.ui
def team_strategy_ui():
    if not _TEND:
        return ui.p("No team history yet — run the scraper.", class_="muted")
    return ui.div(
        ui.input_radio_buttons("view", None,
                               {"team": "Single team", "league": "League comparison"},
                               inline=True),
        ui.panel_conditional(
            "input.view === 'team'",
            ui.input_select("team", "Team", _TEAMS),
            ui.output_ui("team_view"),
        ),
        ui.panel_conditional(
            "input.view === 'league'",
            ui.input_select("metric", "Rank teams by", {
                "pct_college": "College preference",
                "pct_hs": "High-school preference",
                "pct_pitcher": "Pitcher preference",
            }),
            ui.output_ui("league_view"),
        ),
    )


@module.server
def team_strategy_server(input, output, session):
    @render.ui
    def team_view():
        t = _TEND.get(input.team(), {})
        if not t:
            return ui.p("No data.", class_="muted")
        pb = t.get("position_breakdown") or {}
        recent = _HIST[(_HIST["team"] == input.team())] if len(_HIST) else _HIST
        if len(recent):
            recent = recent[recent.get("round").fillna(1) == 1] if "round" in recent else recent
            recent = recent.sort_values(["year", "overall"], ascending=[False, True])
        rows = "".join(
            f'<tr><td>{int(r["year"])}</td><td>{int(r.get("overall", 0)) or ""}</td>'
            f'<td>{r["player"]}</td><td>{r.get("position","")}</td>'
            f'<td>{r.get("school","")}</td><td>{r.get("level","")}</td></tr>'
            for _, r in recent.iterrows()
        ) if len(recent) else ""
        return ui.div(
            ui.div(
                stat_card("1st-round picks", str(t.get("n_picks", "—"))),
                stat_card("College", _pct(t.get("pct_college"))),
                stat_card("High school", _pct(t.get("pct_hs"))),
                stat_card("Pitchers", _pct(t.get("pct_pitcher"))),
                class_="stat-row",
            ),
            ui.h3("Position mix (historical 1st rounders)"),
            bars(sorted(pb.items(), key=lambda kv: -kv[1]), color="#1f6feb") if pb
            else ui.p("—", class_="muted"),
            ui.h3("First-round picks (2018–2025)"),
            ui.HTML('<table class="hist-table"><thead><tr><th>Year</th><th>Overall</th>'
                    '<th>Player</th><th>Pos</th><th>School</th><th>Level</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table>') if rows
            else ui.p("No pick history.", class_="muted"),
        )

    @render.ui
    def league_view():
        m = input.metric()
        pairs = [(team, 100 * float(t.get(m, 0) or 0)) for team, t in _TEND.items()]
        pairs.sort(key=lambda kv: -kv[1])
        return ui.div(
            ui.h3("League-wide tendencies"),
            bars(pairs, suffix="%", color="#d97706"),
        )
