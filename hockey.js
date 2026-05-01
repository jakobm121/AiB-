(function () {
  const safeNumber = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const fmtPercent = value => `${safeNumber(value).toFixed(1)}%`;
  const fmtUnits = value => `${safeNumber(value) > 0 ? '+' : ''}${safeNumber(value).toFixed(1)}u`;
  const fmtOdds = value => safeNumber(value).toFixed(2);
  const setText = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
  const bucketLabel = bucket => bucket === 'over_main_total' ? 'Over Main Total' : bucket === 'under_main_total' ? 'Under Main Total' : (bucket || 'Bucket');

  function setPositiveNegativeClass(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('positive', 'negative');
    const n = safeNumber(value);
    if (n > 0) el.classList.add('positive');
    if (n < 0) el.classList.add('negative');
  }

  function renderOverallStats(stats) {
    const totals = stats.totals || {};
    setText('hero-total-picks', String(safeNumber(totals.total_picks)));
    setText('hero-roi', fmtPercent(totals.roi_percent));
    setText('hero-hit-rate', fmtPercent(totals.hit_rate_percent));
    setText('hero-avg-odds', fmtOdds(totals.avg_odds));
    setText('stat-total-picks', String(safeNumber(totals.total_picks)));
    setText('stat-settled', String(safeNumber(totals.settled_picks)));
    setText('stat-pending', `${safeNumber(totals.pending_picks)} pending`);
    setText('stat-profit', fmtUnits(totals.profit_units));
    setText('stat-roi', fmtPercent(totals.roi_percent));
    setPositiveNegativeClass('stat-profit', totals.profit_units);
    setPositiveNegativeClass('stat-roi', totals.roi_percent);
    const bucketRows = [...(stats.bucket_stats || [])].sort((a,b) => safeNumber(b.roi_percent) - safeNumber(a.roi_percent));
    const leagueRows = [...(stats.league_stats || [])].sort((a,b) => safeNumber(b.roi_percent) - safeNumber(a.roi_percent));
    setText('hero-best-bucket', bucketRows.length ? bucketLabel(bucketRows[0].bucket) : 'Building sample');
    setText('hero-best-league', leagueRows.length ? leagueRows[0].league : 'Building sample');
  }

  function renderTable(bodyId, rows, type) {
    const body = document.getElementById(bodyId);
    if (!body) return;
    if (!rows || !rows.length) {
      body.innerHTML = `<tr><td colspan="6">No settled ${type} stats yet.</td></tr>`;
      return;
    }
    body.innerHTML = rows.map(row => {
      const name = type === 'bucket' ? bucketLabel(row.bucket) : row.league;
      return `
        <tr>
          <td>${name}</td>
          <td>${safeNumber(row.picks)}</td>
          <td>${fmtPercent(row.hit_rate_percent)}</td>
          <td>${fmtOdds(row.avg_odds)}</td>
          <td class="${safeNumber(row.profit_units) >= 0 ? 'positive' : 'negative'}">${fmtUnits(row.profit_units)}</td>
          <td class="${safeNumber(row.roi_percent) >= 0 ? 'positive' : 'negative'}">${fmtPercent(row.roi_percent)}</td>
        </tr>`;
    }).join('');
  }

  function renderPredictions(payload) {
    const container = document.getElementById('today-picks');
    if (!container) return;
    const entries = Object.entries(payload.buckets || {}).filter(([, picks]) => Array.isArray(picks) && picks.length);
    if (!entries.length) {
      container.innerHTML = '<article class="card prediction-item"><h4>No hockey picks available right now.</h4><p class="muted">The model did not find any valid picks in the current window.</p></article>';
      return;
    }
    container.innerHTML = entries.map(([bucket, picks]) => `
      <div class="bucket-block">
        <div class="bucket-head"><h3>${bucketLabel(bucket)}</h3><span>${picks.length}</span></div>
        <div class="pick-list">
          ${picks.map(pick => `
            <article class="card prediction-item">
              <div class="prediction-top"><span class="tag">${pick.bet || '-'}</span><span>${pick.league || '-'} · ${pick.time || '-'}</span></div>
              <h4>${pick.match || 'Unknown match'}</h4>
              <div class="prediction-meta-grid">
                <div><small>Odds</small><strong>${fmtOdds(pick.odds)}</strong></div>
                <div><small>Goal Edge</small><strong>${safeNumber(pick.goal_edge).toFixed(2)}</strong></div>
                <div><small>Confidence</small><strong>${safeNumber(pick.confidence_score).toFixed(1)}</strong></div>
                <div><small>Quality</small><strong>${safeNumber(pick.quality_score).toFixed(1)}</strong></div>
              </div>
              <details><summary>Detailed AI analysis</summary><p>${pick.reasoning || 'No analysis available.'}</p></details>
            </article>`).join('')}
        </div>
      </div>`).join('');
  }

  async function loadStats() {
    try {
      const res = await fetch('./hockey_stats.json', { cache: 'no-store' });
      const stats = await res.json();
      renderOverallStats(stats);
      renderTable('bucket-stats-body', stats.bucket_stats || [], 'bucket');
      renderTable('league-stats-body', stats.league_stats || [], 'league');
    } catch (err) { console.warn('Could not load hockey_stats.json', err); }
  }

  async function loadPredictions() {
    try {
      const res = await fetch('./hockey_predictions.json', { cache: 'no-store' });
      const payload = await res.json();
      renderPredictions(payload);
      if (payload.generated_at) {
        const dt = new Date(payload.generated_at);
        setText('last-updated', `Updated • ${dt.toLocaleDateString('en-GB')} • ${dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
        setText('hero-updated', dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
      }
    } catch (err) { console.warn('Could not load hockey_predictions.json', err); }
  }

  document.addEventListener('DOMContentLoaded', () => { loadStats(); loadPredictions(); });
})();
