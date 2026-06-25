import { saveDraft } from './storage.js';

function esc(s) {
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Mulberry32 seeded RNG (reproducible from seed)
function mulberry32(seed) {
  let s = seed >>> 0;
  return function() {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function uniform(rng, lo, hi) { return lo + rng() * (hi - lo); }

function posGroup(pos) {
  pos = (pos || '').toUpperCase();
  if (['RHP','LHP','P'].includes(pos)) return 'P';
  if (pos === 'C') return 'C';
  if (pos === 'OF') return 'OF';
  return 'IF';
}

function needFactor(tend, player, takenGroups) {
  if (!tend) return 1.0;
  const grp = posGroup(player.position || '');
  const isPitcher = grp === 'P';
  const pctP = parseFloat(tend.pct_pitcher || 0.5) || 0.5;
  const lean = isPitcher ? pctP : (1.0 - pctP);
  let factor = 1.0 - 0.18 * (lean - 0.5);
  const pb = tend.position_breakdown || {};
  const total = Object.values(pb).reduce((a,b) => a+b, 0) || 1;
  const grpShare = (pb[grp] || 0) / total;
  factor *= 1.0 - 0.12 * (grpShare - 0.25);
  factor *= 1.0 + 0.06 * (takenGroups[grp] || 0);
  return factor;
}

function simulate(board, order, tendencies, { mode='realistic', randomness=0.15, seed=0, locked={} } = {}) {
  const rng = mulberry32(seed);
  const avail = new Map(board.map(p => [p.player_id, p]));
  const takenGroups = {};
  const results = [];

  for (const slot of order) {
    const pickNo = slot.pick, team = slot.team || '';
    const forcedId = locked[pickNo] || locked[String(pickNo)];
    let chosen = null, isManual = false;

    if (forcedId && avail.has(forcedId)) {
      chosen = avail.get(forcedId);
      isManual = true;
    } else if (avail.size > 0) {
      const tg = (takenGroups[team] = takenGroups[team] || {});
      const scored = [];
      for (const p of avail.values()) {
        const cr = p.consensus_rank || 9999;
        let score = cr;
        if (mode !== 'bpa') {
          score = cr * needFactor(tendencies[team], p, tg);
          if (mode === 'realistic' && randomness > 0) {
            score *= 1.0 + uniform(rng, -randomness, randomness);
          }
        }
        scored.push([score, p]);
      }
      scored.sort((a,b) => a[0]-b[0]);
      chosen = scored[0][1];
    }

    if (!chosen) continue;
    avail.delete(chosen.player_id);
    const grp = posGroup(chosen.position || '');
    const tg = (takenGroups[team] = takenGroups[team] || {});
    tg[grp] = (tg[grp] || 0) + 1;

    const cr = chosen.consensus_rank;
    results.push({
      pick: pickNo, team,
      player: chosen.player || '',
      position: chosen.position || '',
      school: chosen.school || '',
      class_level: chosen.class_level || '',
      consensus_rank: cr,
      value: (typeof cr === 'number' && pickNo) ? (cr - pickNo) : null,
      player_id: chosen.player_id,
      manual: isManual,
    });
  }
  return results;
}

export function initSimulator(G, showModal) {
  const el = document.getElementById('tab-simulator');
  const order = G.draft_order;
  const teams = [...new Set(order.map(s => s.team))].sort();
  const defaultSeed = Math.floor(Math.random() * 100000);

  el.innerHTML = `
    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:flex-end;margin-bottom:1rem;">
      <div>
        <label class="control-label">Your team</label>
        <select id="sim-team" class="form-select" style="width:220px;">
          <option value="">(none — full sim)</option>
          ${teams.map(t => `<option>${esc(t)}</option>`).join('')}
        </select>
      </div>
      <div>
        <label class="control-label">Mode</label>
        <select id="sim-mode" class="form-select" style="width:160px;">
          <option value="realistic">Realistic</option>
          <option value="bpa">Best Player Available</option>
          <option value="team_need">Team Need</option>
        </select>
      </div>
      <div>
        <label class="control-label">Randomness</label>
        <input type="range" id="sim-rand" min="0" max="0.5" step="0.05" value="0.15" style="width:120px;vertical-align:middle;margin-left:.4rem;">
        <span id="sim-rand-val" style="font-family:'JetBrains Mono',monospace;margin-left:.3rem;">0.15</span>
      </div>
      <div>
        <label class="control-label">Seed</label>
        <input type="number" id="sim-seed" class="form-control" value="${defaultSeed}" style="width:110px;">
      </div>
      <button id="sim-start" class="btn btn-primary" style="align-self:flex-end;">Start Simulation</button>
    </div>
    <div id="sim-clock"></div>
    <div id="sim-results"></div>
    <div id="sim-save-area" style="display:none;margin-top:1rem;"></div>
  `;

  el.querySelector('#sim-rand').addEventListener('input', e => {
    el.querySelector('#sim-rand-val').textContent = e.target.value;
  });

  let state = null; // {order, committed, myTeam, mode, randomness, seed}

  function getOpts() {
    return {
      myTeam: el.querySelector('#sim-team').value,
      mode: el.querySelector('#sim-mode').value,
      randomness: parseFloat(el.querySelector('#sim-rand').value),
      seed: parseInt(el.querySelector('#sim-seed').value, 10) || 0,
    };
  }

  function nextMyPick(results, committed, myTeam) {
    if (!myTeam) return null;
    for (const slot of order) {
      if (slot.team !== myTeam) continue;
      if (committed[slot.pick] || committed[String(slot.pick)]) continue;
      // check if this slot has been reached in results
      const done = results.find(r => r.pick === slot.pick);
      if (!done) return slot.pick;
    }
    return null;
  }

  function renderClock(pickNo, results, committed) {
    const clockEl = document.getElementById('sim-clock');
    const avail = G.consensus.filter(p => !results.some(r => r.player_id === p.player_id));

    clockEl.innerHTML = `
      <div class="clock-box">
        <div style="font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-bottom:.3rem;">On the Clock — Pick #${pickNo}</div>
        <div style="margin-bottom:.6rem;">
          <input type="text" id="sim-search" class="form-control" placeholder="Search players…" autocomplete="off" style="max-width:340px;">
        </div>
        <div id="sim-pick-list" class="sim-pick-list"></div>
        <div style="margin-top:.7rem;display:flex;align-items:center;gap:.7rem;">
          <span id="sim-pick-name" style="font-size:.88rem;color:var(--accent);min-width:160px;"></span>
          <button id="sim-draft-btn" class="btn btn-primary btn-sm" disabled>Draft Player</button>
        </div>
      </div>`;

    let selectedPid = null;
    const listEl = document.getElementById('sim-pick-list');
    const searchEl = document.getElementById('sim-search');
    const nameEl = document.getElementById('sim-pick-name');
    const draftBtn = document.getElementById('sim-draft-btn');

    function renderList() {
      const q = searchEl.value.trim().toLowerCase();
      const top = avail.filter(p => !q || p.player.toLowerCase().includes(q) || (p.school||'').toLowerCase().includes(q)).slice(0,30);
      listEl.innerHTML = top.map(p => `
        <div class="sim-pick-row${p.player_id === selectedPid ? ' selected' : ''}" data-pid="${esc(p.player_id)}"
          style="${p.player_id === selectedPid ? 'background:var(--accent-bg);border-color:var(--accent);' : ''}">
          <span style="font-family:'JetBrains Mono',monospace;color:var(--accent);margin-right:.5rem;">#${p.consensus_rank}</span>
          <strong>${esc(p.player)}</strong>
          <span class="muted"> · ${esc(p.position)} · ${esc(p.school)}</span>
        </div>`).join('');
      listEl.querySelectorAll('[data-pid]').forEach(row => {
        row.addEventListener('click', () => {
          selectedPid = row.dataset.pid;
          const p = G.consensus.find(x => x.player_id === selectedPid);
          nameEl.textContent = p ? p.player : '';
          draftBtn.disabled = false;
          renderList();
        });
      });
    }
    searchEl.addEventListener('input', renderList);
    renderList();

    draftBtn.addEventListener('click', () => {
      if (!selectedPid) return;
      state.committed[pickNo] = selectedPid;
      runSim();
    });
  }

  function runSim() {
    const results = simulate(G.consensus, order, G.tendencies, {
      mode: state.mode,
      randomness: state.randomness,
      seed: state.seed,
      locked: state.committed,
    });

    const myPick = nextMyPick(results, state.committed, state.myTeam);

    if (myPick) {
      // Run sim up to (but not including) myPick
      const partial = results.filter(r => r.pick < myPick);
      renderResults(partial, true);
      renderClock(myPick, partial, state.committed);
    } else {
      renderResults(results, false);
      document.getElementById('sim-clock').innerHTML = results.length
        ? `<p class="clock-done" style="margin:.5rem 0;">Draft complete!</p>` : '';
      renderSaveArea(results);
    }
  }

  function renderResults(results, partial) {
    const resEl = document.getElementById('sim-results');
    if (!results.length) { resEl.innerHTML = ''; return; }
    const rows = results.map(r => {
      const isMe = r.team === state.myTeam;
      const valClass = r.value === null ? '' : r.value > 0 ? 'val-neg' : r.value < 0 ? 'val-pos' : '';
      const valStr = r.value === null ? '' : (r.value > 0 ? `+${r.value}` : String(r.value));
      return `<tr class="${isMe ? 'sim-you' : ''}${r.manual ? ' sim-locked' : ' sim-proj'}">
        <td style="font-family:'JetBrains Mono',monospace;color:var(--accent);">${r.pick}</td>
        <td class="muted" style="font-size:.8rem;text-align:left;">${esc(r.team)}</td>
        <td style="text-align:left;cursor:pointer;font-weight:600;" data-pid="${esc(r.player_id)}">${esc(r.player)}</td>
        <td class="bb-pos">${esc(r.position)}</td>
        <td class="muted" style="font-size:.8rem;text-align:left;">${esc(r.school)}</td>
        <td class="muted">${r.consensus_rank || ''}</td>
        <td class="${valClass}" style="font-family:'JetBrains Mono',monospace;">${valStr}</td>
      </tr>`;
    }).join('');
    resEl.innerHTML = `<div class="sim-wrap"><table class="sim-table">
      <thead><tr><th>Pick</th><th>Team</th><th>Player</th><th>Pos</th><th>School</th><th>Cons.</th><th>Value</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
    resEl.querySelectorAll('[data-pid]').forEach(td => {
      td.addEventListener('click', () => showModal(td.dataset.pid));
    });
  }

  function renderSaveArea(results) {
    if (!results.length) return;
    const area = document.getElementById('sim-save-area');
    area.style.display = '';
    area.innerHTML = `
      <hr>
      <div style="display:flex;gap:.8rem;flex-wrap:wrap;align-items:flex-end;">
        <div>
          <label class="control-label">Draft name</label>
          <input type="text" id="sim-save-name" class="form-control" placeholder="My 2026 Mock Draft" style="width:240px;">
        </div>
        <div>
          <label class="control-label">Author</label>
          <input type="text" id="sim-save-author" class="form-control" placeholder="Your name" style="width:160px;">
        </div>
        <button id="sim-save-btn" class="btn btn-primary btn-sm">Save Draft</button>
        <span id="sim-save-status" style="font-size:.82rem;color:var(--muted);"></span>
      </div>`;

    document.getElementById('sim-save-btn').addEventListener('click', async () => {
      const name = document.getElementById('sim-save-name').value.trim();
      const author = document.getElementById('sim-save-author').value.trim();
      if (!name) { alert('Please enter a draft name.'); return; }
      const btn = document.getElementById('sim-save-btn');
      btn.disabled = true;
      btn.textContent = 'Saving…';
      try {
        await saveDraft({
          draftName: name,
          author: author || 'Anonymous',
          mode: state.mode,
          seed: state.seed,
          picks: results.map(r => ({ pick: r.pick, team: r.team, player_id: r.player_id, player: r.player, position: r.position })),
        });
        document.getElementById('sim-save-status').textContent = 'Draft saved!';
        btn.textContent = 'Saved';
      } catch(e) {
        document.getElementById('sim-save-status').textContent = 'Error: ' + e.message;
        btn.disabled = false;
        btn.textContent = 'Save Draft';
      }
    });
  }

  el.querySelector('#sim-start').addEventListener('click', () => {
    const opts = getOpts();
    state = { ...opts, committed: {} };
    document.getElementById('sim-save-area').style.display = 'none';
    runSim();
  });
}
