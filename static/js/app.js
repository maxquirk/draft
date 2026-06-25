import { buildModal } from './modal.js';
import { initBigboard } from './bigboard.js';
import { initSearch } from './search.js';
import { initProjections } from './projections.js';
import { initSimulator } from './simulator.js';
import { initTeam } from './team.js';
import { initCommunity } from './community.js';

const DATA = 'data/';
const FILES = ['consensus','draft_order','projections','tendencies','history','grades','stats'];

async function fetchAll() {
  const results = await Promise.all(FILES.map(f => fetch(DATA + f + '.json').then(r => r.json())));
  const [consensus_raw, draft_order, projections, tendencies, history, grades, stats] = results;
  return {
    consensus: consensus_raw.players,
    source_keys: consensus_raw.source_keys,
    draft_order,
    projections,
    tendencies,
    history,
    grades,
    stats,
  };
}

// Bootstrap modal instance
let bsModal = null;

function showModal(playerId, G) {
  const { title, bodyHtml } = buildModal(playerId, G);
  document.getElementById('player-modal-title').textContent = title;
  document.getElementById('player-modal-body').innerHTML = bodyHtml;
  if (!bsModal) bsModal = new bootstrap.Modal(document.getElementById('playerModal'));
  bsModal.show();
}

// Tab switching
function initTabs() {
  document.querySelectorAll('[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
  });
}

async function main() {
  initTabs();

  let G;
  try {
    G = await fetchAll();
  } catch(e) {
    document.getElementById('tab-rankings').innerHTML = `<p style="color:var(--bad);padding:2rem;">Failed to load data: ${e.message}</p>`;
    return;
  }

  const modal = (pid) => showModal(pid, G);

  initBigboard(G, modal);
  initSearch(G, modal);
  initProjections(G, modal);
  initSimulator(G, modal);
  initTeam(G);
  initCommunity(G);
}

main();
