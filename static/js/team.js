function esc(s) {
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function hbar(label, value, color='var(--accent)') {
  const pct = Math.round(value * 100);
  return `<div class="hbar-row">
    <span>${esc(label)}</span>
    <div class="hbar-track"><span class="hbar-fill" style="width:${pct}%;background:${color};"></span></div>
    <span class="hbar-val">${pct}%</span>
  </div>`;
}

export function initTeam(G) {
  const el = document.getElementById('tab-teams');
  const teams = Object.keys(G.tendencies).sort();

  el.innerHTML = `
    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:flex-end;margin-bottom:1rem;">
      <div>
        <label class="control-label">Team</label>
        <select id="tm-team" class="form-select" style="width:220px;">
          ${teams.map(t => `<option>${esc(t)}</option>`).join('')}
        </select>
      </div>
      <div>
        <label class="control-label">View</label>
        <select id="tm-view" class="form-select" style="width:180px;">
          <option value="team">Team Profile</option>
          <option value="league">League Comparison</option>
        </select>
      </div>
    </div>
    <div id="tm-content"></div>
  `;

  function renderTeam(teamName) {
    const t = G.tendencies[teamName];
    if (!t) { document.getElementById('tm-content').innerHTML = '<p class="muted">No data.</p>'; return; }

    const hist = G.history.filter(h => h.team === teamName).sort((a,b) => b.year - a.year || a.overall - b.overall);
    const histRows = hist.map(h => `<tr>
      <td style="font-family:'JetBrains Mono',monospace;color:var(--accent);">${h.year}</td>
      <td style="font-family:'JetBrains Mono',monospace;">${h.overall}</td>
      <td class="muted">${esc(h.round)}</td>
      <td style="text-align:left;font-weight:600;">${esc(h.player)}</td>
      <td class="bb-pos">${esc(h.position)}</td>
      <td style="text-align:left;font-size:.8rem;" class="muted">${esc(h.school)}</td>
    </tr>`).join('');

    const pb = t.position_breakdown || {};
    const pbTotal = Object.values(pb).reduce((a,b)=>a+b,0) || 1;
    const posBars = Object.entries(pb).sort((a,b)=>b[1]-a[1])
      .map(([pos, n]) => hbar(pos, n/pbTotal, 'var(--link)')).join('');

    document.getElementById('tm-content').innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:1.2rem;margin-bottom:1rem;">
        <div class="stat-card"><div class="stat-value">${t.n_picks}</div><div class="stat-label">Picks tracked</div></div>
        <div class="stat-card"><div class="stat-value">${Math.round(t.pct_pitcher*100)}%</div><div class="stat-label">Pitchers</div></div>
        <div class="stat-card"><div class="stat-value">${Math.round(t.pct_college*100)}%</div><div class="stat-label">College</div></div>
        <div class="stat-card"><div class="stat-value">${Math.round(t.pct_hs*100)}%</div><div class="stat-label">High School</div></div>
      </div>
      <div class="hbar" style="margin-bottom:1.2rem;">
        ${hbar('Pitchers', t.pct_pitcher)}
        ${hbar('Hitters', 1 - t.pct_pitcher, 'var(--good)')}
        ${hbar('College', t.pct_college, 'var(--link)')}
        ${hbar('High School', t.pct_hs, 'var(--bad)')}
      </div>
      ${posBars ? `<h3>Position Breakdown</h3><div class="hbar">${posBars}</div>` : ''}
      ${histRows ? `<h3>Draft History</h3>
        <div class="bb-wrap"><table class="bb-table"><thead>
          <tr><th>Year</th><th>Overall</th><th>Round</th><th>Player</th><th>Pos</th><th>School</th></tr>
        </thead><tbody>${histRows}</tbody></table></div>` : ''}`;
  }

  function renderLeague() {
    const sorted = Object.entries(G.tendencies)
      .filter(([,t]) => t.n_picks >= 5)
      .sort((a,b) => b[1].pct_pitcher - a[1].pct_pitcher);

    const rows = sorted.map(([team, t]) => `
      <div class="hbar-row" style="grid-template-columns:160px 1fr 55px;">
        <span style="font-size:.83rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(team)}</span>
        <div class="hbar-track" style="position:relative;">
          <span class="hbar-fill" style="width:${Math.round(t.pct_pitcher*100)}%;background:var(--accent);"></span>
        </div>
        <span class="hbar-val">${Math.round(t.pct_pitcher*100)}%</span>
      </div>`).join('');

    document.getElementById('tm-content').innerHTML = `
      <h3>Pitcher Draft Rate by Team</h3>
      <p class="muted" style="font-size:.82rem;margin-bottom:.75rem;">Teams with 5+ tracked picks.</p>
      <div class="hbar" style="max-width:600px;">${rows}</div>`;
  }

  function update() {
    const view = el.querySelector('#tm-view').value;
    if (view === 'league') {
      renderLeague();
    } else {
      renderTeam(el.querySelector('#tm-team').value);
    }
  }

  el.querySelector('#tm-team').addEventListener('change', update);
  el.querySelector('#tm-view').addEventListener('change', update);
  update();
}
