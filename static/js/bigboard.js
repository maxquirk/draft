const SOURCE_LABELS = {
  mlb_pipeline: 'MLB Pipeline', baseball_america: 'BA', espn_mcdaniel: 'ESPN/McDaniel',
  keith_law: 'Keith Law', just_baseball: 'Just Baseball', perfect_game: 'Perfect Game',
  fangraphs: 'FanGraphs', overslot: 'Overslot', eleven_point7: '11point7',
};
const SRC_PRIORITY = ['mlb_pipeline','baseball_america','overslot'];

function esc(s) {
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function srcLabel(k) {
  return SOURCE_LABELS[k] || k.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
}

export function initBigboard(G, showModal) {
  const el = document.getElementById('tab-rankings');
  const players = G.consensus;
  const keys = G.source_keys;

  el.innerHTML = `
    <div style="margin-bottom:1rem;">
      <label class="control-label">Players to show (by consensus rank)</label>
      <input type="range" id="bb-topn" min="10" max="${Math.max(players.length,20)}" value="${Math.min(40,players.length)}" style="width:260px;vertical-align:middle;margin-left:.5rem;">
      <span id="bb-topn-val" style="font-family:'JetBrains Mono',monospace;margin-left:.4rem;">${Math.min(40,players.length)}</span>
    </div>
    <p class="muted" style="font-size:.82rem;margin-bottom:.6rem;">Green = this board notably higher than consensus; red = notably lower. · = not ranked.</p>
    <div id="bb-matrix"></div>
    <h3 style="margin-top:1.5rem;">Biggest disagreements</h3>
    <p class="muted" style="font-size:.82rem;margin-bottom:.6rem;">Players the boards most disagree on — standard deviation of rank across boards.</p>
    <div id="bb-disagree"></div>
  `;

  function renderMatrix(topn) {
    const d = players.slice(0, topn);
    const head = `<th>Rank</th><th>Player</th><th class="bb-pos">Pos</th>` +
      keys.map(k => `<th class="bb-src">${esc(srcLabel(k))}</th>`).join('') +
      `<th class="bb-sd">SD</th>`;
    const body = d.map(p => {
      const cr = p.consensus_rank;
      const cells = keys.map(k => {
        const v = p.sources[k];
        if (v == null) return `<td class="bb-na">·</td>`;
        const diff = cr - v;
        const cls = diff >= 15 ? 'bb-hi' : diff <= -15 ? 'bb-lo' : '';
        return `<td class="${cls}">${v}</td>`;
      }).join('');
      return `<tr>
        <td class="bb-rank">${cr}</td>
        <td class="bb-name" style="cursor:pointer" data-pid="${esc(p.player_id)}">${esc(p.player)}</td>
        <td class="bb-pos">${esc(p.position)}</td>
        ${cells}
        <td class="bb-sd">${p.stdev.toFixed(1)}</td>
      </tr>`;
    }).join('');
    document.getElementById('bb-matrix').innerHTML =
      `<div class="bb-wrap"><table class="bb-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
    document.getElementById('bb-matrix').querySelectorAll('[data-pid]').forEach(el => {
      el.addEventListener('click', () => showModal(el.dataset.pid));
    });
  }

  function renderDisagree() {
    const d = players.filter(p => p.n_sources >= 2).sort((a,b) => b.stdev - a.stdev).slice(0,40);
    const head = `<tr><th>Cons.</th><th>Player</th><th>Pos</th><th>School</th><th>Best</th><th>Worst</th><th>Spread</th><th>SD</th><th>Boards</th></tr>`;
    const body = d.map(p => `<tr style="cursor:pointer" data-pid="${esc(p.player_id)}">
      <td class="bb-rank">${p.consensus_rank}</td>
      <td class="bb-name">${esc(p.player)}</td>
      <td class="bb-pos">${esc(p.position)}</td>
      <td style="text-align:left;font-size:.82rem;">${esc(p.school)}</td>
      <td>${p.best_rank}</td><td>${p.worst_rank}</td><td>${p.worst_rank - p.best_rank}</td>
      <td class="bb-sd">${p.stdev.toFixed(1)}</td><td>${p.n_sources}</td>
    </tr>`).join('');
    document.getElementById('bb-disagree').innerHTML =
      `<div class="bb-wrap"><table class="bb-table"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
    document.getElementById('bb-disagree').querySelectorAll('[data-pid]').forEach(el => {
      el.addEventListener('click', () => showModal(el.dataset.pid));
    });
  }

  const slider = el.querySelector('#bb-topn');
  const label  = el.querySelector('#bb-topn-val');
  slider.addEventListener('input', () => { label.textContent = slider.value; renderMatrix(+slider.value); });

  renderMatrix(+slider.value);
  renderDisagree();
}
