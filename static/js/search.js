const RECENT_KEY = 'draft2026_recent';

function esc(s) {
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function getRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); } catch { return []; }
}
function addRecent(pid) {
  const r = [pid, ...getRecent().filter(x => x !== pid)].slice(0, 8);
  localStorage.setItem(RECENT_KEY, JSON.stringify(r));
}

function playerCard(p, showModal) {
  return `<div class="player-card" style="cursor:pointer" data-pid="${esc(p.player_id)}">
    <div>
      <span class="src-chip">#${p.consensus_rank}</span>
      <strong>${esc(p.player)}</strong>
      <span class="muted"> · ${esc(p.position)}</span>
    </div>
    <div class="muted" style="font-size:.83rem;">${esc(p.school)}</div>
  </div>`;
}

export function initSearch(G, showModal) {
  const el = document.getElementById('tab-search');
  el.innerHTML = `
    <div style="max-width:460px;margin-bottom:1.2rem;">
      <input type="text" id="search-q" class="form-control" placeholder="Search by name or school…" autocomplete="off">
    </div>
    <div id="search-results"></div>
  `;

  const input = el.querySelector('#search-q');
  const results = el.querySelector('#search-results');

  function render() {
    const q = input.value.trim().toLowerCase();
    let html = '';
    let pids = [];

    if (q.length >= 2) {
      const hits = G.consensus.filter(p =>
        p.player.toLowerCase().includes(q) || (p.school||'').toLowerCase().includes(q)
      ).slice(0, 20);
      if (!hits.length) {
        html = `<p class="muted">No players found.</p>`;
      } else {
        pids = hits.map(p => p.player_id);
        html = `<div class="player-card-grid">${hits.map(p => playerCard(p)).join('')}</div>`;
      }
    } else {
      const recent = getRecent();
      if (!recent.length) {
        html = `<p class="muted">Search for a player above to see their scouting profile.</p>`;
      } else {
        const recPlayers = recent.map(pid => G.consensus.find(p => p.player_id === pid)).filter(Boolean);
        html = `
          <p class="muted" style="font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;margin-bottom:.6rem;">Recent</p>
          <div class="player-card-grid">${recPlayers.map(p => playerCard(p)).join('')}</div>`;
      }
    }
    results.innerHTML = html;
    results.querySelectorAll('[data-pid]').forEach(card => {
      card.addEventListener('click', () => { addRecent(card.dataset.pid); showModal(card.dataset.pid); });
    });
  }

  input.addEventListener('input', render);
  render();
}
