const SOURCE_LABELS = {
  mlb_pipeline: 'MLB Pipeline', baseball_america: 'BA', espn_mcdaniel: 'ESPN/McDaniel',
  keith_law: 'Keith Law', just_baseball: 'Just Baseball', perfect_game: 'Perfect Game',
  fangraphs: 'FanGraphs', overslot: 'Overslot', eleven_point7: '11point7',
};

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function notBlank(v) {
  return v !== undefined && v !== null && String(v).trim() !== '' && String(v).trim() !== 'nan';
}

function gradeColor(v) {
  const n = parseInt(v, 10);
  if (isNaN(n)) return 'var(--muted)';
  if (n >= 55) return 'var(--good)';
  if (n >= 45) return 'var(--accent)';
  return 'var(--muted)';
}

function gradeChip(label, value) {
  if (!notBlank(value)) return '';
  const v = String(value).trim();
  const color = gradeColor(v);
  return `<span class="src-chip" style="color:${color};font-family:'JetBrains Mono',monospace;font-weight:700;">${esc(label)} <span style="color:var(--ink)">${esc(v)}</span></span>`;
}

export function buildModal(playerId, G) {
  const player = G.consensus.find(p => p.player_id === playerId);
  if (!player) return { title: 'Unknown', bodyHtml: '<p>Player not found.</p>' };

  const p = player;
  const title = `${esc(p.player)}  ·  ${esc(p.position)}  ·  ${esc(p.school)}`;

  // Consensus chips
  const sourceEntries = Object.entries(p.sources || {}).sort((a,b) => a[1]-b[1]);
  const sourceLabel = k => SOURCE_LABELS[k] || k.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
  const chips = sourceEntries.length
    ? sourceEntries.map(([k,v]) => `<span class="src-chip">${esc(sourceLabel(k))}: #${v}</span>`).join('')
    : `<span class="muted">No source ranks available.</span>`;

  const subtitleParts = [p.class_level, p.state].filter(notBlank);
  const subtitle = subtitleParts.length ? `<p class="muted">${esc(subtitleParts.join(' · '))}</p>` : '';
  const notes = notBlank(p.notes) ? `<p class="muted">${esc(p.notes)}</p>` : '';

  // Grades section
  let gradesHtml = '';
  const gr = G.grades[playerId];
  if (gr) {
    const isPitcher = /RHP|LHP|P/.test((p.position||'').toUpperCase());
    let toolChips = '';
    if (isPitcher) {
      const fbVelo = notBlank(gr.fb_velo) ? `${gr.fb_velo} mph` : '';
      toolChips = [
        gradeChip('FB', gr.fb_grade),
        fbVelo ? gradeChip(fbVelo, gr.fb_grade) : '',
        gradeChip('CB', gr.cb_grade),
        gradeChip('SL', gr.sl_grade),
        gradeChip('CH', gr.ch_grade),
        gradeChip('CTL', gr.control),
      ].filter(Boolean).join('');
    } else {
      toolChips = [
        gradeChip('HIT', gr.hit),
        gradeChip('PWR', gr.power),
        gradeChip('RUN', gr.run),
        gradeChip('ARM', gr.arm),
        gradeChip('FLD', gr.field),
      ].filter(Boolean).join('');
    }

    const fv = notBlank(gr.fv) ? String(gr.fv).trim() : '';
    const physParts = [
      notBlank(gr.height) ? gr.height : '',
      notBlank(gr.weight) && gr.weight !== 'nan' ? `${gr.weight} lbs` : '',
      (notBlank(gr.bats) && notBlank(gr.throws)) ? `B/T: ${gr.bats}/${gr.throws}` : '',
    ].filter(Boolean);

    gradesHtml = `<hr><h4 style="font-size:.95rem;margin-bottom:.5rem;">Scouting Profile</h4>`;
    if (fv) {
      gradesHtml += `<div style="margin-bottom:.6rem;"><span class="big-chip">FV ${esc(fv)}</span>${toolChips ? `<span class="chip-row" style="display:inline-flex">${toolChips}</span>` : ''}</div>`;
    } else if (toolChips) {
      gradesHtml += `<div class="chip-row">${toolChips}</div>`;
    }
    if (physParts.length) gradesHtml += `<p class="muted" style="font-size:.83rem;margin:.25rem 0;">${esc(physParts.join(' · '))}</p>`;
    if (notBlank(gr.commits_to)) gradesHtml += `<p class="muted" style="font-size:.83rem;margin:.3rem 0;">Committed to: ${esc(gr.commits_to)}</p>`;
    if (notBlank(gr.writeup)) gradesHtml += `<p style="font-size:.84rem;line-height:1.55;margin:.5rem 0;">${esc(gr.writeup)}</p>`;
  }

  // Projection section
  let projHtml = '';
  const pr = (G.projections.players || []).find(x => x.player_id === playerId);
  if (pr) {
    const landing = (pr.landing || []).slice(0,3).map(l =>
      `<b>#${l.pick}</b> ${esc(l.team)} <span class="muted">${Math.round(100*l.pct)}%</span>`
    ).join(' · ');
    projHtml = `<hr><h4 style="font-size:.95rem;margin-bottom:.5rem;">Draft Projection</h4>
      <div>
        <span class="big-chip">Proj. pick #${pr.proj_pick}</span>
        <span class="src-chip">Range ${pr.proj_low}–${pr.proj_high}</span>
      </div>
      ${landing ? `<p><span class="muted" style="font-size:.85rem;">Top landing spots: ${landing}</span></p>` : ''}`;
  }

  // Stats section
  let statsHtml = '';
  const st = G.stats[playerId];
  if (st) {
    const type = String(st.stat_type||'').toUpperCase();
    const cards = type === 'BATTER'
      ? [['AVG',st.avg],['OBP',st.obp],['SLG',st.slg],['OPS',st.ops],['HR',st.hr],['RBI',st.rbi],['SB',st.sb]]
      : [['ERA',st.era],['WHIP',st.whip],['K/9',st.k_9],['BB/9',st.bb_9],['IP',st.ip],['W',st.w],['SV',st.sv]];
    const cardHtml = cards.filter(([,v]) => notBlank(v))
      .map(([lbl,v]) => `<div class="stat-card"><div class="stat-value">${esc(v)}</div><div class="stat-label">${esc(lbl)}</div></div>`)
      .join('');
    if (cardHtml) {
      statsHtml = `<hr><h4 style="font-size:.95rem;margin-bottom:.5rem;">2026 Stats (${esc(type)})</h4><div class="stat-row">${cardHtml}</div>`;
    }
  }

  const brUrl = `https://www.baseball-reference.com/search/search.fcgi?search=${encodeURIComponent(p.player)}`;

  const bodyHtml = `
    <div class="detail-card" style="border:none;padding:0;margin:0;">
      <div style="margin-bottom:.7rem;">
        <span class="big-chip">Consensus #${p.consensus_rank}</span>
        <span class="src-chip">avg ${p.avg_rank}</span>
        <span class="src-chip">range ${p.best_rank}–${p.worst_rank}</span>
        <span class="src-chip">volatility ${p.stdev}</span>
        <span class="src-chip">${p.n_sources} boards</span>
      </div>
      ${subtitle}${notes}
      <hr>
      <h4 style="font-size:.95rem;margin-bottom:.5rem;">Board Rankings</h4>
      <div class="chip-row">${chips}</div>
      ${gradesHtml}
      ${projHtml}
      ${statsHtml}
      <hr>
      <a href="${brUrl}" target="_blank" class="btn btn-outline-secondary btn-sm" style="font-size:.8rem;">Baseball-Reference ↗</a>
    </div>`;

  return { title, bodyHtml };
}
