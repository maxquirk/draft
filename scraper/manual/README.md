# Manual data drop-in

Some boards sit behind a Cloudflare "managed challenge" (notably **FanGraphs**)
that automated scrapers can't pass. Use your own browser — which already passes
the challenge — and drop the exported file here.

## FanGraphs The Board
1. Open https://www.fangraphs.com/prospects/the-board/2026-mlb-draft
2. Click **Export Data** (top-right of the board) to download the CSV.
3. Save it here as `fangraphs_board.csv`.
4. Re-run `python -m scraper.run` — the adapter ingests it automatically.

### Alternative: cf_clearance cookie (advanced)
In a browser that has passed the FanGraphs challenge, copy the `cf_clearance`
cookie value and the browser's User-Agent, then:

```bash
export FANGRAPHS_CF_CLEARANCE="<cookie value>"
export FANGRAPHS_UA="<exact browser User-Agent>"
python -m scraper.run
```

The cookie is IP- and UA-bound and expires, so the CSV route is more durable.
