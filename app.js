const DATA_PATHS = {
  stats: ['data/totals_stats.json', 'public/data/totals_stats.json', '/data/totals_stats.json'],
  results: ['data/totals_results.json', 'public/data/totals_results.json', '/data/totals_results.json'],
  picks: ['data/totals_predictions.json', 'public/data/totals_predictions.json', '/data/totals_predictions.json']
};

const PLATFORMS = [
  {
    name: 'Sportaza', rating: '4.8', bonus: '100% do €100', url: 'https://stzns.naralvin.com', editor: true,
    pros: ['Pouzdani depoziti i brže isplate', '24/7 podrška', 'Pregledno sučelje', 'Dobra promo sekcija', 'Više jezika'],
    bonuses: ['Bet builder risk-free ponude', 'Weekly reload', 'Cashback opcije', 'Boosted odds', 'Sports i casino promo sekcije']
  },
  {
    name: '20Bet', rating: '4.6', bonus: '100% do €120', url: 'https://promo.20bet.partners',
    pros: ['Brz mobilni doživljaj', 'Dobre live opcije', 'Konkurentne kvote', 'Više načina plaćanja', '24/7 podrška'],
    bonuses: ['Saturday reload', 'Boosted odds', 'Multi-bet insurance', 'Tournament promo', 'Casino ponude']
  },
  {
    name: '22Bet', rating: '4.5', bonus: '100% do €122', url: 'https://moy.auraodin.com',
    pros: ['Širok izbor sportova i marketa', 'Dobra live sekcija', 'Mobilno sučelje', 'Česte promocije', 'Više jezika podrške'],
    bonuses: ['Friday reload', 'App bonus', 'Accumulator of the day', 'Weekly rebate', 'Birthday bonus']
  },
  {
    name: '1xBet', rating: '4.2', bonus: '100% do €100', url: 'https://refpa649012.pro',
    pros: ['Velika sportska ponuda', 'Mnogo specijalnih marketa', 'Live chat', 'Redovne promocije', 'Širok izbor kvota'],
    bonuses: ['Advance bet', 'App bonus', 'No-risk opcije', 'Birthday free bet', 'Accumulator boost']
  },
  {
    name: '7Signs', rating: '4.4', bonus: '100% do €100', url: 'https://sgn.naralvin.com',
    pros: ['Više welcome ponuda', 'Crypto opcije', 'Jednostavan dizajn', 'Gamification elementi', 'Prijateljska podrška'],
    bonuses: ['Weekly reload', 'Cashback', 'Accumulator boost', 'Boosted odds', 'Horse racing promo']
  },
  {
    name: '5Gringos', rating: '4.3', bonus: '100% do €100', url: 'https://fgrns.naralvin.com',
    pros: ['Pouzdane isplate', 'Solidna welcome ponuda', 'Crypto rewards', 'Lako sučelje', 'Aktivne weekly ponude'],
    bonuses: ['Crypto bonus', 'Risk-free opcije', 'Weekly cashback', '2 goals ahead', 'Enhanced odds']
  },
  {
    name: 'Woosports', rating: '4.2', bonus: '200% do €1000', url: 'https://mu.fastmui.com',
    pros: ['Live streaming', 'Široka sportska ponuda', 'Brze transakcije', '24/7 podrška', 'Weekly reloads'],
    bonuses: ['Second deposit bonus', 'Comboboost', 'Friday freebet', 'Monthly promo', 'Casino ponude']
  }
];

function fmtNumber(value, suffix = '') {
  if (value === undefined || value === null || value === '') return '—';
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  return `${num.toLocaleString('bs-BA', { maximumFractionDigits: 3 })}${suffix}`;
}

function fmtProfit(value) {
  if (value === undefined || value === null) return '—';
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return `${num >= 0 ? '+' : ''}${num.toLocaleString('bs-BA', { maximumFractionDigits: 3 })}u`;
}

async function fetchFirst(paths) {
  for (const path of paths) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (res.ok) return await res.json();
    } catch (_) {}
  }
  return null;
}

function setupMenu() {
  const btn = document.querySelector('[data-menu-toggle]');
  const nav = document.querySelector('[data-nav]');
  if (!btn || !nav) return;
  btn.addEventListener('click', () => nav.classList.toggle('open'));
}

function setupAccordions() {
  document.querySelectorAll('[data-accordion]').forEach(btn => {
    btn.addEventListener('click', () => {
      const panel = document.getElementById(btn.dataset.accordion);
      if (!panel) return;
      panel.classList.toggle('open');
      const span = btn.querySelector('span');
      if (span) span.textContent = panel.classList.contains('open') ? '−' : '＋';
    });
  });
}

function fillStats(stats) {
  if (!stats) return;
  document.querySelectorAll('[data-stat]').forEach(el => {
    const key = el.dataset.stat;
    const value = stats[key];
    if (key === 'profit') el.textContent = fmtProfit(value);
    else if (key === 'roi' || key === 'win_rate') el.textContent = fmtNumber(value, '%');
    else if (key === 'total_staked') el.textContent = `${fmtNumber(value)}u`;
    else el.textContent = fmtNumber(value);
  });
}

function tableFromGroup(group) {
  if (!group || typeof group !== 'object') return '<p class="micro-note">Nema podataka.</p>';
  const rows = Object.entries(group).map(([name, s]) => `
    <tr>
      <td><strong>${name}</strong></td>
      <td>${s.wins ?? 0}-${s.losses ?? 0}</td>
      <td>${fmtProfit(s.profit)}</td>
      <td>${fmtNumber(s.roi, '%')}</td>
      <td>${s.total_picks ?? 0}</td>
    </tr>`).join('');
  return `<table class="data-table"><thead><tr><th>Segment</th><th>W-L</th><th>Profit</th><th>ROI</th><th>Pickovi</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function fillDetailTables(stats) {
  if (!stats) return;
  document.querySelectorAll('[data-table]').forEach(el => {
    el.innerHTML = tableFromGroup(stats[el.dataset.table]);
  });
}

function dailyStats(results) {
  const days = new Map();
  (results || []).forEach(item => {
    const result = String(item.result || '').toLowerCase();
    if (!['win','loss'].includes(result)) return;
    const date = item.date || 'unknown';
    if (!days.has(date)) days.set(date, { total_picks: 0, wins: 0, losses: 0, profit: 0, staked: 0 });
    const d = days.get(date);
    d.total_picks += 1;
    if (result === 'win') d.wins += 1;
    if (result === 'loss') d.losses += 1;
    d.profit += Number(item.public_profit ?? item.profit ?? 0);
    d.staked += Number(item.public_stake ?? item.stake ?? 0);
  });
  return Array.from(days.entries()).sort((a,b) => b[0].localeCompare(a[0])).map(([date, d]) => ({ date, ...d, roi: d.staked ? (d.profit / d.staked) * 100 : 0 }));
}

function fillDailyTable(results) {
  const el = document.querySelector('[data-daily-table]');
  if (!el) return;
  const rows = dailyStats(results).map(d => `
    <tr><td><strong>${d.date}</strong></td><td>${d.wins}-${d.losses}</td><td>${fmtProfit(d.profit)}</td><td>${fmtNumber(d.roi, '%')}</td><td>${d.total_picks}</td></tr>
  `).join('');
  el.innerHTML = rows ? `<table class="data-table"><thead><tr><th>Dan</th><th>W-L</th><th>Profit</th><th>ROI</th><th>Pickovi</th></tr></thead><tbody>${rows}</tbody></table>` : '<p class="micro-note">Dnevna statistika nije dostupna.</p>';
}

function drawProfitChart(results) {
  const canvas = document.getElementById('profitChart');
  if (!canvas || !Array.isArray(results)) return;
  const countEl = document.querySelector('[data-results-count]');
  if (countEl) countEl.textContent = `${results.length} rezultata`;
  const ctx = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * ratio;
  canvas.height = rect.height * ratio;
  ctx.scale(ratio, ratio);
  ctx.clearRect(0,0,rect.width,rect.height);
  const sorted = results.slice().filter(x => ['win','loss','push','void'].includes(String(x.result||'').toLowerCase())).sort((a,b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
  let cum = 0;
  const points = sorted.map((r, i) => {
    cum += Number(r.public_profit ?? r.profit ?? 0);
    return { x: i, y: cum };
  });
  if (!points.length) return;
  const pad = 26;
  const minY = Math.min(0, ...points.map(p => p.y));
  const maxY = Math.max(0, ...points.map(p => p.y));
  const spanY = maxY - minY || 1;
  const xFor = i => pad + (i / Math.max(1, points.length - 1)) * (rect.width - pad*2);
  const yFor = y => rect.height - pad - ((y - minY) / spanY) * (rect.height - pad*2);
  ctx.strokeStyle = 'rgba(239,227,202,.12)'; ctx.lineWidth = 1;
  for(let i=0;i<4;i++){ const y=pad+i*(rect.height-pad*2)/3; ctx.beginPath(); ctx.moveTo(pad,y); ctx.lineTo(rect.width-pad,y); ctx.stroke(); }
  ctx.strokeStyle = '#c8a75f'; ctx.lineWidth = 3; ctx.beginPath();
  points.forEach((p,i) => { const x=xFor(i), y=yFor(p.y); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); }); ctx.stroke();
  ctx.fillStyle = 'rgba(241,223,184,.95)';
  const last = points[points.length-1]; ctx.beginPath(); ctx.arc(xFor(points.length-1), yFor(last.y), 4, 0, Math.PI*2); ctx.fill();
  ctx.fillStyle = 'rgba(170,163,154,.9)'; ctx.font = '12px Inter, sans-serif';
  ctx.fillText(`Start 0u`, pad, rect.height - 8);
  ctx.fillText(`Final ${fmtProfit(last.y)}`, Math.max(pad, rect.width - 120), 18);
}

function renderPicks(picks) {
  const root = document.querySelector('[data-picks]');
  if (!root) return;
  if (!Array.isArray(picks) || !picks.length) {
    root.innerHTML = '<div class="empty-state">Trenutno nema aktivnih public pickova. Kada filter pronađe kvalitetan signal, kartice će se pojaviti ovdje.</div>';
    return;
  }
  root.innerHTML = picks.map(p => `
    <article class="pick-card">
      <div class="pick-top"><span>${p.tournament || 'Tennis'}</span><span>${p.date || ''} ${p.time || ''}</span></div>
      <h3>${p.match || 'Match'}</h3>
      <span class="pick-bet">${p.bet || `${String(p.side||'').toUpperCase()} ${p.line}`}</span>
      <div class="pick-meta">
        <div><span>Kvota</span><strong>${fmtNumber(p.odds)}</strong></div>
        <div><span>Ulog</span><strong>${fmtNumber(p.public_stake ?? p.stake)}u</strong></div>
        <div><span>Snaga</span><strong>${p.public_stake_label || p.stake_label || 'Standard'}</strong></div>
        <div><span>Edge</span><strong>${fmtNumber((Number(p.edge)||0)*100, '%')}</strong></div>
      </div>
      <a class="btn btn-gold" href="https://stzns.naralvin.com" target="_blank" rel="nofollow sponsored noopener">Preporučena platforma</a>
    </article>
  `).join('');
}

function renderPlatforms() {
  const root = document.querySelector('[data-platforms]');
  if (!root) return;
  root.innerHTML = PLATFORMS.map((p, idx) => `
    <article class="platform-card ${p.editor ? 'editor' : ''}">
      <p class="eyebrow">${p.bonus}</p>
      <h3>${p.name}</h3>
      <span class="rating">${p.rating}/5</span>
      <p>Provjerena partnerska opcija za pregled kvota, marketa i promo ponuda.</p>
      <div class="platform-actions">
        <a class="btn btn-gold" href="${p.url}" target="_blank" rel="nofollow sponsored noopener">Pogledaj ponudu</a>
        <button class="details-toggle" data-platform-detail="${idx}">Detalji ↓</button>
      </div>
      <div class="platform-details" id="platform-detail-${idx}">
        <h4>Prednosti</h4><ul>${p.pros.map(x => `<li>${x}</li>`).join('')}</ul>
        <h4>Promo sekcija</h4><ul>${p.bonuses.map(x => `<li>${x}</li>`).join('')}</ul>
      </div>
    </article>
  `).join('');
  document.querySelectorAll('[data-platform-detail]').forEach(btn => {
    btn.addEventListener('click', () => {
      const panel = document.getElementById(`platform-detail-${btn.dataset.platformDetail}`);
      panel?.classList.toggle('open');
      btn.textContent = panel?.classList.contains('open') ? 'Zatvori ↑' : 'Detalji ↓';
    });
  });
}

async function initData() {
  const page = document.body.dataset.page;
  const stats = await fetchFirst(DATA_PATHS.stats);
  fillStats(stats);
  if (page === 'prognoze') {
    fillDetailTables(stats);
    const results = await fetchFirst(DATA_PATHS.results) || [];
    fillDailyTable(results);
    drawProfitChart(results);
    window.addEventListener('resize', () => drawProfitChart(results));
    const picks = await fetchFirst(DATA_PATHS.picks) || [];
    renderPicks(picks);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupMenu();
  setupAccordions();
  renderPlatforms();
  initData();
});
