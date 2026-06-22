# ⚾ 2026 MLB Draft Hub

A self-contained, GitHub-hosted site for researching the **2026 MLB Draft**: an
aggregated consensus big board built from many public rankings, a mock-draft
simulator, big-board disagreement analysis, and historical team draft tendencies.

The site is a **Shiny for Python** app exported with **shinylive**, so it runs
entirely in the browser (Python compiled to WebAssembly via Pyodide) — **no server,
no backend, free static hosting on GitHub Pages.**

## How it works (two tiers)

```
scraper/  (offline)            app/  (in-browser)              docs/ (deployed)
requests + Selenium + bs4  ->  Shiny for Python reads     ->   shinylive export
many big boards                only app/data/*.json             static WASM site
   |                                  ^
   +---- writes app/data/*.json ------+
```

The browser can't scrape, so scraping is an **offline pipeline** that writes small
static JSON files into `app/data/`. The Shiny app only reads those files.

## Features

| Tab | What it does |
|-----|--------------|
| **Prospect Explorer** | Search/filter every 2026-eligible player; click for each board's rank. |
| **Big Board** | Consensus vs every source, with disagreement (volatility) highlighting. |
| **Mock Simulator** | Auto-sim or go on-the-clock for one team; engine blends consensus with each team's historical lean. Export CSV. |
| **Team Strategy** | Per-team historical position/level tendencies; league-wide comparison. |

## Data sources

Free, auto-scraped: **MLB.com Pipeline, FanGraphs The Board, Perfect Game,
Just Baseball, 11Point7**. Best-effort via public archives (Wayback / archive.today):
**ESPN+/Kiley McDaniel, The Athletic/Keith Law, Baseball America**. Team draft history
and the projected draft order come from **Baseball-Reference**.

Coverage is never hidden — the **About** tab shows each source's status and player
count from the last scrape (`app/data/run_report.json`). Paywalled gaps appear there
rather than being silently dropped. Rankings are stored as factual data points
attributed to their source; this is an educational/research project.

> The 2026 draft order is a **standings-inverse projection** (worst 2025 record picks
> first), not the official lottery order.

## Local development

```bash
# 1. environment (uv)
uv venv
uv pip install -e ".[scraper,dev]"

# 2. refresh the data (offline; needs Chrome for the dynamic/paywalled sources)
python -m scraper.run

# 3. run the app
shiny run app/app.py            # http://127.0.0.1:8000

# 4. build the static site and preview it
shinylive export app docs
python -m http.server -d docs 8080   # http://127.0.0.1:8080
```

## Deploying to GitHub Pages

Two workflows are included:

- **`.github/workflows/deploy.yml`** — on every push to `main` that touches `app/`,
  exports the app and publishes it to Pages (via the official Pages artifact flow).
  Enable it once under **Settings → Pages → Source: GitHub Actions**.
- **`.github/workflows/scrape.yml`** — weekly (and on demand) re-runs the scraper,
  commits changed `app/data/*.json`, and the resulting push triggers a redeploy.

`docs/` is the build output (~43MB Pyodide runtime) and is **gitignored** — the
deploy workflow rebuilds it in CI, so it never needs to be committed.

**Manual alternative** (no Actions): run `shinylive export app docs`, force-add it
with `git add -f docs`, commit, and set **Settings → Pages → Source: Deploy from
branch → main /docs**.

## Adding a new big board

1. Create `scraper/sources/<key>.py` exposing `SOURCE = SourceMeta(...)` and
   `fetch() -> list[dict]` (use `ranking_row(...)` from `scraper/base.py`).
2. Register it in `scraper/config.py`.
3. Re-run `python -m scraper.run`. Name canonicalization, consensus, and the UI pick
   it up automatically.
