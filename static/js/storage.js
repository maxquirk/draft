import { DRAFT_PAT, GITHUB_REPO, GITHUB_BRANCH, DRAFTS_PATH } from './config.js';

const API = `https://api.github.com/repos/${GITHUB_REPO}/contents/${DRAFTS_PATH}`;
const HEADERS = {
  'Authorization': `Bearer ${DRAFT_PAT}`,
  'Accept': 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
};

async function getFile() {
  const r = await fetch(`${API}?ref=${GITHUB_BRANCH}`, { headers: HEADERS });
  if (!r.ok) throw new Error(`GitHub GET ${r.status}`);
  const j = await r.json();
  const content = atob(j.content.replace(/\n/g,''));
  return { sha: j.sha, content };
}

async function putFile(content, sha, message) {
  const r = await fetch(API, {
    method: 'PUT',
    headers: { ...HEADERS, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message, content: btoa(unescape(encodeURIComponent(content))),
      sha, branch: GITHUB_BRANCH,
    }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(`GitHub PUT ${r.status}: ${err.message||''}`);
  }
  return (await r.json()).content.sha;
}

function csvRow(cells) {
  return cells.map(v => {
    const s = String(v ?? '');
    if (s.includes(',') || s.includes('"') || s.includes('\n')) return `"${s.replace(/"/g,'""')}"`;
    return s;
  }).join(',');
}

function parseRows(csv) {
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.trim());
  return lines.slice(1).map(line => {
    const cells = parseCsvLine(line);
    const obj = {};
    headers.forEach((h, i) => { obj[h] = (cells[i] ?? '').trim(); });
    return obj;
  });
}

function parseCsvLine(line) {
  const cells = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQ) {
      if (c === '"' && line[i+1] === '"') { cur += '"'; i++; }
      else if (c === '"') { inQ = false; }
      else { cur += c; }
    } else if (c === '"') { inQ = true; }
    else if (c === ',') { cells.push(cur); cur = ''; }
    else { cur += c; }
  }
  cells.push(cur);
  return cells;
}

const CSV_HEADERS = ['draft_id','draft_name','author','saved_at','mode','seed','picks_json','upvotes','downvotes'];

export async function saveDraft({ draftName, author, mode, seed, picks }) {
  const { sha, content } = await getFile();
  const rows = parseRows(content);

  const draft_id = `${Date.now()}_${Math.random().toString(36).slice(2,7)}`;
  const saved_at = new Date().toISOString().replace('T',' ').slice(0,19);
  const picks_json = JSON.stringify(picks);

  rows.push({ draft_id, draft_name: draftName, author, saved_at, mode: String(mode), seed: String(seed), picks_json, upvotes: '0', downvotes: '0' });

  const newCsv = [CSV_HEADERS.join(','), ...rows.map(r => csvRow(CSV_HEADERS.map(h => r[h]||'')))].join('\n') + '\n';
  await putFile(newCsv, sha, `Add draft: ${draftName}`);
  return draft_id;
}

export async function loadDrafts() {
  const RAW = `https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/${DRAFTS_PATH}`;
  const r = await fetch(RAW);
  if (!r.ok) throw new Error(`Fetch drafts ${r.status}`);
  return parseRows(await r.text());
}
