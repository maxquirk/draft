import { GITHUB_REPO, GITHUB_BRANCH, DRAFTS_PATH } from './config.js';

function esc(s) {
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function parseCsvLine(line) {
  const cells = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQ) {
      if (c === '"' && line[i+1] === '"') { cur += '"'; i++; }
      else if (c === '"') { inQ = false; }
      else cur += c;
    } else if (c === '"') { inQ = true; }
    else if (c === ',') { cells.push(cur); cur = ''; }
    else cur += c;
  }
  cells.push(cur);
  return cells;
}

function parseCsv(text) {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.trim());
  return lines.slice(1).map(line => {
    const cells = parseCsvLine(line);
    const obj = {};
    headers.forEach((h, i) => { obj[h] = (cells[i] ?? '').trim(); });
    return obj;
  });
}

export function initCommunity(G) {
  const el = document.getElementById('tab-community');
  el.innerHTML = `
    <div style="display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-end;margin-bottom:1rem;">
      <div>
        <label class="control-label">Sort</label>
        <select id="cd-sort" class="form-select" style="width:180px;">
          <option value="recent">Most Recent</option>
          <option value="oldest">Oldest</option>
        </select>
      </div>
      <button id="cd-refresh" class="btn btn-outline-secondary btn-sm">Refresh</button>
    </div>
    <div id="cd-list"><p class="muted">Loading drafts…</p></div>
  `;

  let drafts = [];
  let expanded = new Set();

  async function load() {
    const raw = `https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/${DRAFTS_PATH}`;
    try {
      const r = await fetch(raw + '?t=' + Date.now());
      if (!r.ok) throw new Error(`${r.status}`);
      drafts = parseCsv(await r.text());
    } catch(e) {
      document.getElementById('cd-list').innerHTML = `<p style="color:var(--bad);">Failed to load drafts: ${esc(e.message)}</p>`;
      return;
    }
    render();
  }

  function render() {
    const sort = el.querySelector('#cd-sort').value;
    let d = [...drafts];
    if (sort === 'oldest') d.sort((a,b) => (a.saved_at||'').localeCompare(b.saved_at||''));
    else d.sort((a,b) => (b.saved_at||'').localeCompare(a.saved_at||''));

    if (!d.length) {
      document.getElementById('cd-list').innerHTML = '<p class="muted">No community drafts yet.</p>';
      return;
    }

    const cards = d.map(draft => {
      const id = esc(draft.draft_id);
      const isExpanded = expanded.has(draft.draft_id);

      let picks = [];
      try { picks = JSON.parse(draft.picks_json || '[]'); } catch {}
      const preview = picks.slice(0,5).map((pk,i) => `<b>${pk.pick||i+1}.</b> ${esc(pk.player||pk.player_id||'?')}`).join(' &nbsp;');

      let detailHtml = '';
      if (isExpanded && picks.length) {
        const rows = picks.map(pk => `<tr>
          <td style="font-family:'JetBrains Mono',monospace;color:var(--accent);">${pk.pick||''}</td>
          <td style="text-align:left;" class="muted">${esc(pk.team||'')}</td>
          <td style="text-align:left;font-weight:600;">${esc(pk.player||pk.player_id||'')}</td>
          <td class="bb-pos">${esc(pk.position||'')}</td>
        </tr>`).join('');
        detailHtml = `<div class="cd-detail"><div class="bb-wrap"><table class="bb-table">
          <thead><tr><th>Pick</th><th>Team</th><th>Player</th><th>Pos</th></tr></thead>
          <tbody>${rows}</tbody></table></div></div>`;
      }

      return `<div class="cd-card" data-cdid="${id}">
        <div class="cd-header">
          <div class="cd-meta">
            <div class="cd-title">${esc(draft.draft_name||'Untitled')}</div>
            <div class="cd-byline muted">${esc(draft.author||'Anonymous')} &nbsp;·&nbsp; ${esc(draft.saved_at||'')} &nbsp;·&nbsp; mode: ${esc(draft.mode||'')}</div>
          </div>
          <div class="cd-actions">
            <button class="cd-expand" data-cdid="${id}">${isExpanded ? 'Collapse' : 'Expand'}</button>
          </div>
        </div>
        <div class="cd-preview">${preview}</div>
        ${detailHtml}
      </div>`;
    }).join('');

    document.getElementById('cd-list').innerHTML = `<div class="cd-list">${cards}</div>`;

    document.getElementById('cd-list').querySelectorAll('.cd-expand').forEach(btn => {
      btn.addEventListener('click', () => {
        const cdid = drafts.find(x => x.draft_id === btn.dataset.cdid)?.draft_id;
        if (!cdid) return;
        if (expanded.has(cdid)) expanded.delete(cdid);
        else expanded.add(cdid);
        render();
      });
    });
  }

  el.querySelector('#cd-sort').addEventListener('change', render);
  el.querySelector('#cd-refresh').addEventListener('click', () => { expanded.clear(); load(); });
  load();
}
