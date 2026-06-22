"""2026 MLB Draft Hub — Shiny for Python entry point.

Static, serverless: exported with `shinylive export app docs` and hosted on GitHub
Pages. All data is the pre-scraped JSON in app/data/ (see the scraper/ pipeline).
"""
from pathlib import Path

from shiny import App, ui

from logic import dataio
from modules.bigboard import bigboard_server, bigboard_ui
from modules.explorer import explorer_server, explorer_ui
from modules.projections import projections_server, projections_ui
from modules.simulator import simulator_server, simulator_ui
from modules.team_strategy import team_strategy_server, team_strategy_ui

CSS = Path(__file__).parent / "www" / "styles.css"


def about_panel():
    rep = dataio.report()
    rows = []
    for s in rep.get("sources", []):
        ok = s["status"] == "ok"
        cls = "cov-ok" if ok else "cov-gap"
        rows.append(
            f'<tr><td>{s["name"]}</td><td>{s["access"]}</td>'
            f'<td class="{cls}">{s["status"]}</td><td>{s["rows"]}</td></tr>'
        )
    cov = ('<table class="cov-table"><thead><tr><th>Source</th><th>Access</th>'
           '<th>Status</th><th>Players</th></tr></thead><tbody>'
           + "".join(rows) + "</tbody></table>") if rows else "<p>No scrape run yet.</p>"
    return ui.div(
        ui.h3("What this is"),
        ui.p("An aggregated, source-attributed view of the 2026 MLB Draft class: a "
             "consensus big board built from multiple public rankings, a mock-draft "
             "simulator, and historical team draft tendencies."),
        ui.h3("Methodology"),
        ui.tags.ul(
            ui.tags.li("Consensus rank = weighted average of each board's rank, with a "
                       "soft penalty for players covered by fewer boards."),
            ui.tags.li("'Volatility' (SD) measures how much the boards disagree on a player."),
            ui.tags.li("The simulator blends the consensus board with each team's historical "
                       "position/level tendencies, plus optional unpredictability."),
            ui.tags.li("The simulator uses the actual 2026 first-round order (post Dec 2025 "
                       "lottery), including Competitive Balance Round A and PPI/penalty picks."),
        ),
        ui.h3("Source coverage (last scrape)"),
        ui.p(f"Generated: {rep.get('generated_at', 'never')} · "
             f"{rep.get('n_players', 0)} players on the board", class_="muted"),
        ui.HTML(cov),
        ui.h3("Caveats"),
        ui.p("Paywalled boards (ESPN+, The Athletic, Baseball America) are best-effort via "
             "public archives; gaps are shown above rather than hidden. Rankings are factual "
             "data points attributed to their source. Educational / research use.",
             class_="muted"),
        class_="detail-card",
    )


app_ui = ui.page_navbar(
    ui.nav_panel("Prospect Explorer", explorer_ui("explorer")),
    ui.nav_panel("Big Board", bigboard_ui("bigboard")),
    ui.nav_panel("Projections", projections_ui("proj")),
    ui.nav_panel("Mock Simulator", simulator_ui("sim")),
    ui.nav_panel("Team Strategy", team_strategy_ui("teams")),
    ui.nav_panel("About", about_panel()),
    title="⚾ 2026 MLB Draft Hub",
    id="nav",
    # Bootstrap 5.3's built-in dark mode (no SASS compile -> works in shinylive/Pyodide).
    # Setting the attribute in <head> applies it before first paint (no flash).
    header=ui.head_content(
        ui.tags.script("document.documentElement.setAttribute('data-bs-theme','dark');"),
        ui.include_css(CSS),
    ),
    fillable=False,
)


def server(input, output, session):
    explorer_server("explorer")
    bigboard_server("bigboard")
    projections_server("proj")
    simulator_server("sim")
    team_strategy_server("teams")


app = App(app_ui, server)
