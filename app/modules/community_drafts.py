"""Community Drafts tab — cards with likes/dislikes and sort."""
from __future__ import annotations

import html
import json

from shiny import module, reactive, render, req, ui


def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _parse_picks(raw: str) -> list[dict]:
    try:
        return json.loads(raw)
    except Exception:
        return []


def _sort_drafts(rows: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "oldest":
        return sorted(rows, key=lambda r: r.get("saved_at", ""))
    if sort_by == "upvotes":
        return sorted(rows, key=lambda r: _safe_int(r.get("upvotes", 0)), reverse=True)
    if sort_by == "downvotes":
        return sorted(rows, key=lambda r: _safe_int(r.get("downvotes", 0)), reverse=True)
    # default: most recent
    return sorted(rows, key=lambda r: r.get("saved_at", ""), reverse=True)


def _draft_card_html(d: dict, expanded: bool, ns_up: str, ns_dn: str, ns_exp: str) -> str:
    picks = _parse_picks(d.get("picks_json", "[]"))
    n_picks = len(picks)
    up = _safe_int(d.get("upvotes", 0))
    dn = _safe_int(d.get("downvotes", 0))
    did = d.get("draft_id", "")

    e = html.escape  # shorthand — escape all user-supplied strings before HTML insertion

    top5 = " &nbsp;·&nbsp; ".join(
        f"<b>{p['pick']}.</b> {e(str(p.get('player','?')))} "
        f"<span class='muted'>({e(str(p.get('position','')))})</span>"
        for p in picks[:5]
    )

    detail = ""
    if expanded and picks:
        rows_html = "".join(
            f"<tr>"
            f"<td class='bb-rank'>{p.get('pick','')}</td>"
            f"<td>{e(str(p.get('team','')))}</td>"
            f"<td style='text-align:left;font-weight:600'>{e(str(p.get('player','')))}</td>"
            f"<td class='bb-pos'>{e(str(p.get('position','')))}</td>"
            f"<td style='text-align:left'>{e(str(p.get('school','')))}</td>"
            f"<td>{p.get('consensus_rank','')}</td>"
            f"</tr>"
            for p in picks
        )
        detail = (
            "<div class='cd-detail'>"
            "<div class='sim-wrap'><table class='sim-table'><thead><tr>"
            "<th>Pick</th><th>Team</th><th>Player</th><th>Pos</th><th>School</th><th>Cons.</th>"
            "</tr></thead><tbody>" + rows_html + "</tbody></table></div></div>"
        )

    exp_label = "▲ Hide" if expanded else "▼ Picks"

    return (
        f"<div class='cd-card'>"
        f"<div class='cd-header'>"
        f"<div class='cd-meta'>"
        f"<span class='cd-title'>{e(d.get('draft_name','Untitled'))}</span>"
        f"<span class='muted cd-byline'> · {e(d.get('author','?'))} · {e(d.get('saved_at',''))} · {e(d.get('mode',''))} · {n_picks} picks</span>"
        f"</div>"
        f"<div class='cd-actions'>"
        f"<button class='cd-vote cd-up' onclick=\"Shiny.setInputValue('{ns_up}', '{did}', {{priority:'event'}});\">▲ {up}</button>"
        f"<button class='cd-vote cd-dn' onclick=\"Shiny.setInputValue('{ns_dn}', '{did}', {{priority:'event'}});\">▼ {dn}</button>"
        f"<button class='cd-expand' onclick=\"Shiny.setInputValue('{ns_exp}', '{did}', {{priority:'event'}});\">{exp_label}</button>"
        f"</div>"
        f"</div>"
        f"<div class='cd-preview'>{top5}</div>"
        f"{detail}"
        f"</div>"
    )


@module.ui
def community_drafts_ui():
    return ui.div(
        ui.div(
            ui.h3("Community Mock Drafts", style="margin:0;"),
            ui.input_action_button("refresh", "Refresh", class_="btn-sm"),
            style="display:flex;align-items:center;gap:1rem;margin-bottom:.8rem;",
        ),
        ui.div(
            ui.input_radio_buttons(
                "sort_by", None,
                choices={"recent": "Most Recent", "oldest": "Oldest",
                         "upvotes": "Most Liked", "downvotes": "Most Disliked"},
                selected="recent", inline=True,
            ),
            style="margin-bottom:1rem;",
        ),
        ui.output_ui("draft_list"),
    )


@module.server
def community_drafts_server(input, output, session):
    drafts: reactive.Value[list[dict]] = reactive.Value([])
    expanded_id: reactive.Value[str | None] = reactive.Value(None)
    load_counter: reactive.Value[int] = reactive.Value(0)
    load_error: reactive.Value[str] = reactive.Value("")

    ns_up  = session.ns("upvote")
    ns_dn  = session.ns("downvote")
    ns_exp = session.ns("expand_draft")

    @reactive.effect
    @reactive.event(input.refresh, ignore_none=False)
    async def _load():
        from logic.github_storage import load_drafts
        load_error.set("")
        load_counter.set(load_counter() + 1)
        try:
            result = await load_drafts()
            drafts.set(result)
        except Exception as e:
            load_error.set(str(e))
            drafts.set([])

    @reactive.effect
    @reactive.event(input.expand_draft)
    def _on_expand():
        did = input.expand_draft()
        if not did:
            return
        with reactive.isolate():
            current = expanded_id()
        expanded_id.set(None if current == did else did)

    @reactive.effect
    @reactive.event(input.upvote)
    async def _on_upvote():
        did = input.upvote()
        if not did:
            return
        from logic.github_storage import vote_draft, load_drafts
        await vote_draft(did, "up")
        try:
            drafts.set(await load_drafts())
        except Exception:
            pass

    @reactive.effect
    @reactive.event(input.downvote)
    async def _on_downvote():
        did = input.downvote()
        if not did:
            return
        from logic.github_storage import vote_draft, load_drafts
        await vote_draft(did, "down")
        try:
            drafts.set(await load_drafts())
        except Exception:
            pass

    @render.ui
    def draft_list():
        if load_counter() == 0:
            return ui.p("Click Refresh to load community drafts.", class_="muted")
        err = load_error()
        if err:
            return ui.p(f"Error: {err}", style="color:var(--bad);")
        rows = drafts()
        if not rows:
            return ui.p("No saved drafts yet — be the first!", class_="muted")

        sorted_rows = _sort_drafts(rows, input.sort_by())
        exp = expanded_id()
        cards_html = "".join(
            _draft_card_html(d, d.get("draft_id") == exp, ns_up, ns_dn, ns_exp)
            for d in sorted_rows
        )
        return ui.HTML(f"<div class='cd-list'>{cards_html}</div>")
