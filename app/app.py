"""2026 MLB Draft Hub — Shiny for Python entry point."""
from pathlib import Path

from shiny import App, ui

from modules.bigboard import bigboard_server, bigboard_ui
from modules.community_drafts import community_drafts_server, community_drafts_ui
from modules.explorer import explorer_server, explorer_ui
from modules.projections import projections_server, projections_ui
from modules.simulator import simulator_server, simulator_ui
from modules.team_strategy import team_strategy_server, team_strategy_ui

CSS = Path(__file__).parent / "www" / "styles.css"


def about_panel():
    return ui.div(
        ui.h3("2026 MLB Draft Hub"),
        ui.p("An independent consensus big board for the 2026 MLB Draft class. "
             "Rankings are aggregated from multiple public sources and combined into "
             "a single consensus ordering. The Mock Simulator uses the actual 2026 "
             "post-lottery first-round order."),
        ui.h3("How it works"),
        ui.tags.ul(
            ui.tags.li("Consensus rank = weighted average across board rankings."),
            ui.tags.li("Volatility (SD) = how much the boards disagree on a player."),
            ui.tags.li("The simulator blends the consensus board with each team's "
                       "historical position/level tendencies plus optional unpredictability."),
            ui.tags.li("Draft projections are precomputed: 1,000 Monte Carlo simulations "
                       "over the real 2026 first-round order."),
        ),
        ui.h3("Notes"),
        ui.p("Rankings are factual data points from public sources. "
             "This tool is for research and educational use.",
             class_="muted"),
        class_="detail-card",
    )


app_ui = ui.page_navbar(
    ui.nav_panel("Prospects", explorer_ui("explorer")),
    ui.nav_panel("Rankings", bigboard_ui("bigboard")),
    ui.nav_panel("Projections", projections_ui("proj")),
    ui.nav_panel("Simulator", simulator_ui("sim")),
    ui.nav_panel("Team Strategy", team_strategy_ui("teams")),
    ui.nav_panel("Community Drafts", community_drafts_ui("community")),
    ui.nav_panel("About", about_panel()),
    title="2026 MLB Draft",
    id="nav",
    header=ui.head_content(
        ui.tags.script("document.documentElement.setAttribute('data-bs-theme','dark');"),
        ui.tags.link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap",
        ),
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
    community_drafts_server("community")


app = App(app_ui, server)
