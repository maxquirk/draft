function esc(s) {
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

export function initProjections(G, showModal) {
  const el = document.getElementById('tab-projections');
  const { players, runs } = G.projections;

  const allTeams = [...new Set(players.flatMap(p => (p.landing||[]).map(l => l.team)))].sort();
  const maxPick = Math.max(...players.map(p => p.proj_pick), 40);

  el.innerHTML = `
    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1rem;align-items:flex-end;">
      <div>
        <label class="control-label">Max projected pick</label>
        <input type="range" id="pj-maxpick" min="5" max="${maxPick}" value="${maxPick}" style="width:180px;vertical-align:middle;margin-left:.5rem;">
        <span id="pj-maxpick-val" style="font-family:'JetBrains Mono',monospace;margin-left:.4rem;">${maxPick}</span>
      </div>
      <div>
        <label class="control-label">Filter by team</label>
        <select id="pj-team" class="form-select" style="width:220px;">
          <option value="">(all)</option>
          ${allTeams.map(t => `<option>${esc(t)}</option>`).join('')}
        </select>
      </div>
    </div>
    <div id="pj-table"></div>
  `;

  function render() {
    const maxpick = +el.querySelector('#pj-maxpick').value;
    const team = el.querySelector('#pj-team').value;
    let d = players.filter(p => p.proj_pick <= maxpick);
    if (team) d = d.filter(p => (p.landing||[]).some(l => l.team === team));

    if (!d.length) { document.getElementById('pj-table').innerHTML = `<p class="muted">No players match.</p>`; return; }

    const note = runs ? `<p class="muted" style="font-size:.8rem;">${runs.toLocaleString()} simulations</p>` : '';
    const rows = d.map(p => {
      const spots = (p.landing||[]).map(l =>
        `<b>#${l.pick}</b> ${esc(l.team)} <span class="muted">${Math.round(100*l.pct)}%</span>`
      ).join(' · ');
      return `<tr>
        <td class="pj-pick">${p.proj_pick}</td>
        <td class="pj-name" style="cursor:pointer" data-pid="${esc(p.player_id)}">${esc(p.player)}</td>
        <td>${esc(p.position)}</td>
        <td style="text-align:left">${esc(p.school)}</td>
        <td>${p.consensus_rank}</td>
        <td>${p.proj_low}–${p.proj_high}</td>
        <td style="text-align:left;font-size:.82rem;">${spots}</td>
      </tr>`;
    }).join('');

    document.getElementById('pj-table').innerHTML = note +
      `<div class="sim-wrap"><table class="sim-table"><thead><tr>
        <th>Proj.</th><th>Player</th><th>Pos</th><th>School</th><th>Cons.</th><th>Range</th><th>Top landing spots</th>
      </tr></thead><tbody>${rows}</tbody></table></div>`;

    document.getElementById('pj-table').querySelectorAll('[data-pid]').forEach(td => {
      td.addEventListener('click', () => showModal(td.dataset.pid));
    });
  }

  el.querySelector('#pj-maxpick').addEventListener('input', e => {
    el.querySelector('#pj-maxpick-val').textContent = e.target.value;
    render();
  });
  el.querySelector('#pj-team').addEventListener('change', render);
  render();
}
