const DATA_PATHS = {
  stats: [
    'public/data/totals_stats.json',
    './public/data/totals_stats.json',
    'data/totals_stats.json',
    './data/totals_stats.json'
  ],
  results: [
    'public/data/totals_results.json',
    './public/data/totals_results.json',
    'data/totals_results.json',
    './data/totals_results.json'
  ],
  picks: [
    'public/data/totals_predictions.json',
    './public/data/totals_predictions.json',
    'data/totals_predictions.json',
    './data/totals_predictions.json'
  ]
};

const PARTNERS = {
  sportaza: 'https://stzns.naralvin.com/?mid=309891_1835232',
  bet20: 'https://promo.20bet.partners/redirect.aspx?pid=389482&bid=2044',
  bet22: 'https://moy.auraodin.com/redirect.aspx?pid=148721&bid=1571',
  onexbet: 'https://refpa649012.pro/L?tag=d_4666247m_1599c_&site=4666247&ad=1599',
  sevensigns: 'https://sgn.naralvin.com/?mid=310196_1838281',
  fivegringos: 'https://fgrns.naralvin.com/?mid=309891_1838292',
  woosports: 'https://mu.fastmui.com/redirect.aspx?pid=389482&bid=2112&lpid=1976'
};

const PLATFORM_DATA = [
  {
    name: 'Sportaza',
    tag: 'Editor’s Choice',
    rating: '★★★★★',
    url: PARTNERS.sportaza,
    text: 'Najbolje izbalansirana opcija za početak: jednostavan mobilni flow, solidna tenis ponuda i brzo provjeravanje koef.',
    details: 'AI77 review: testirani su registracija, depozit, bonus aktivacija, tenis marketi, mobilno iskustvo i osnovni payout flow. Sportaza se najbolje uklapa kao glavna platforma za korisnike koji žele čist i brz pristup. Bonusi uključuju welcome ponudu, reload opcije, cashback, boosted odds i crypto bonus. Prije ulaza uvijek provjeri da se linija i koef poklapaju s AI77 pickom.'
  },
  {
    name: '20Bet',
    tag: 'Mobile Flow',
    rating: '★★★★☆',
    url: PARTNERS.bet20,
    text: 'Dobra opcija za korisnike koji žele brz mobilni pregled, live betting i dodatnu provjeru tenis linija.',
    details: 'AI77 review: fokus je bio na brzini depozita, mobilnom iskustvu, live betting sekciji, dostupnosti tenis marketa i promocijama. 20Bet je koristan kao druga platforma u rotaciji kada želiš provjeriti bolji koef ili alternativnu liniju. Dostupne su reload promocije, boosted odds i multi-bet insurance. Kod live marketa koef se može brzo promijeniti.'
  },
  {
    name: '22Bet',
    tag: 'Market Coverage',
    rating: '★★★★☆',
    url: PARTNERS.bet22,
    text: 'Široka sportska ponuda i puno marketa, korisno za usporedbu koef i dodatne opcije prije ulaza.',
    details: 'AI77 review: pregledani su registracija, sportska ponuda, live marketi, mobilni prikaz, support i promo sekcija. 22Bet je dobar izbor kada želiš veću pokrivenost marketa i dodatnu platformu za rotaciju. Bonusi uključuju reload ponude, accumulator promocije, weekly rebate i birthday bonus. Uvijek usporedi liniju s AI77 pickom.'
  },
  {
    name: '1xBet',
    tag: 'Huge Markets',
    rating: '★★★★☆',
    url: PARTNERS.onexbet,
    text: 'Velik izbor sportova i marketa, posebno koristan za traženje alternativnih linija i specifičnih ponuda.',
    details: 'AI77 review: platforma je pregledana kroz market coverage, dostupnost tenis linija, posebne markete, mobilni flow i bonus sekciju. 1xBet može biti koristan za iskusnije korisnike koji žele više opcija, ali dostupnost ovisi o državi. Bonusi uključuju no-risk bet, app promocije, cashback i accumulator boost. Prije korištenja provjeri pravila i ograničenja za svoju lokaciju.'
  },
  {
    name: '7Signs',
    tag: 'Bonus Focused',
    rating: '★★★★☆',
    url: PARTNERS.sevensigns,
    text: 'Dodatna platforma za korisnike koji žele promo value, cashback opcije i crypto bonus mogućnosti.',
    details: 'AI77 review: testiran je osnovni betting flow, depozitno iskustvo, bonus aktivacija, support i pregled sportskih marketa. 7Signs je zanimljiv kao dodatna opcija u rotaciji, posebno za korisnike koji prate reload i cashback promocije. Bonusi uključuju weekly reload, cashback, accumulator boost, boosted odds i horse racing bonus. Kod bonusa uvijek pročitaj wagering uslove.'
  },
  {
    name: '5Gringos',
    tag: 'Promo Rotation',
    rating: '★★★★☆',
    url: PARTNERS.fivegringos,
    text: 'Alternativna opcija za rotaciju platformi, promo ponude, crypto rewards i povremenu provjeru boljih koef.',
    details: 'AI77 review: pregledani su depozit, bonus sekcija, korisničko iskustvo, dostupnost marketa i osnovna isplata. 5Gringos se dobro uklapa kao dodatna platforma, ne nužno kao jedina glavna opcija. Bonusi uključuju crypto rewards, risk-free bet, weekly cashback, early payout i enhanced odds. Najkorisnija je kada tražiš dodatnu vrijednost ili bolju ponudu.'
  },
  {
    name: 'Woosports',
    tag: 'Live Streaming',
    rating: '★★★★☆',
    url: PARTNERS.woosports,
    text: 'Opcija za korisnike koji žele live streaming, sports entertainment flow i dodatne reload promocije.',
    details: 'AI77 review: testirani su registracija, mobilni prikaz, live streaming iskustvo, sportska pokrivenost, support i bonus ponuda. Woosports je dobar dodatak za korisnike koji vole pratiti evente uživo i žele širu ponudu. Bonusi uključuju 200% welcome bonus, second deposit bonus, comboboost i Friday reload freebet. Veći bonusi često imaju strože uslove.'
  }
];

function fmtNumber(value, suffix = '') {
  if (value === undefined || value === null || value === '') return '—';
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  return `${num.toLocaleString('bs-BA', { maximumFractionDigits: 3 })}${suffix}`;
}

function fmtProfit(value) {
  if (value === undefined || value === null || value === '') return '—';
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return `${num >= 0 ? '+' : ''}${num.toLocaleString('bs-BA', { maximumFractionDigits: 3 })}u`;
}

function pctFromProb(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return fmtNumber(n > 1 ? n : n * 100, '%');
}

/* ODIGRANO LOCAL STORAGE */
const PLAYED_PICKS_KEY = 'ai77_played_public_picks';

function getPlayedPicks() {
  try {
    const raw = localStorage.getItem(PLAYED_PICKS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (err) {
    return {};
  }
}

function savePlayedPicks(data) {
  try {
    localStorage.setItem(PLAYED_PICKS_KEY, JSON.stringify(data || {}));
  } catch (err) {}
}

function getPickStorageId(pick) {
  return String(
    pick?.pick_id ||
    pick?.fixture_id ||
    pick?.event_key ||
    `${pick?.date || ''}-${pick?.time || ''}-${pick?.match || ''}-${pick?.bet || ''}`
  );
}

function isPickPlayed(pickId) {
  const played = getPlayedPicks();
  return Boolean(played[String(pickId)]);
}

function togglePickPlayed(pickId) {
  const id = String(pickId || '');
  if (!id) return;

  const played = getPlayedPicks();

  if (played[id]) {
    delete played[id];
  } else {
    played[id] = {
      played_at: new Date().toISOString()
    };
  }

  savePlayedPicks(played);
}

function setupPlayedButtons(picks) {
  document.querySelectorAll('[data-played-toggle]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const pickId = btn.dataset.playedToggle;
      togglePickPlayed(pickId);
      renderPicks(picks);
    });
  });
}

async function fetchFirst(paths) {
  for (const path of paths) {
    try {
      const res = await fetch(`${path}?v=${Date.now()}`, { cache: 'no-store' });
      if (res.ok) return await res.json();
    } catch (err) {}
  }
  return null;
}

function setupMenu() {
  const btn = document.querySelector('[data-menu-toggle]');
  const nav = document.querySelector('[data-nav]');
  if (!btn || !nav) return;
  btn.addEventListener('click', () => nav.classList.toggle('open'));
}

function setupTabs() {
  document.querySelectorAll('[data-tabs]').forEach((wrap) => {
    const buttons = wrap.querySelectorAll('[data-tab]');
    const panels = document.querySelectorAll('[data-tab-panel]');
    buttons.forEach((button) => {
      button.addEventListener('click', () => {
        buttons.forEach((b) => b.classList.remove('active'));
        panels.forEach((p) => p.classList.remove('active'));
        button.classList.add('active');
        const target = document.querySelector(`[data-tab-panel="${button.dataset.tab}"]`);
        if (target) target.classList.add('active');
      });
    });
  });
}

function fillStats(stats) {
  if (!stats) return;
  document.querySelectorAll('[data-stat]').forEach((el) => {
    const key = el.dataset.stat;
    const value = stats[key];
    if (key === 'profit') el.textContent = fmtProfit(value);
    else if (key === 'roi' || key === 'win_rate') el.textContent = fmtNumber(value, '%');
    else if (key === 'total_staked') el.textContent = `${fmtNumber(value)}u`;
    else el.textContent = fmtNumber(value);
  });
  document.querySelectorAll('[data-updated]').forEach((el) => {
    el.textContent = stats.updated_at ? new Date(stats.updated_at).toLocaleString('bs-BA') : '—';
  });
}

function stakeBadgeClass(label) {
  const l = String(label || '').toLowerCase();
  if (l.includes('top')) return 'platinum';
  if (l.includes('strong')) return 'gold';
  return 'silver';
}

function getRotatingPartner(index) {
  const values = Object.values(PARTNERS).filter(Boolean);
  return values[index % values.length] || PARTNERS.sportaza;
}

function renderPicks(picks) {
  const root = document.querySelector('[data-picks]');
  if (!root) return;

  if (!Array.isArray(picks) || !picks.length) {
    root.innerHTML = `
      <article class="empty-card">
        <h3>Nema aktivnih public pickova.</h3>
        <p>AI77 ne forsira selekcije kada filter ne daje dovoljno jak signal. Pogledaj javnu istoriju ili provjeri kasnije.</p>
        <div class="inline-actions" style="justify-content:center">
          <a class="btn primary" href="rezultati.html">Pogledaj rezultate</a>
          <a class="btn" href="platforme.html">Provjerene platforme</a>
        </div>
      </article>
    `;
    return;
  }

  const sorted = picks.slice().sort((a,b) => `${a.date || ''} ${a.time || ''}`.localeCompare(`${b.date || ''} ${b.time || ''}`));

  root.innerHTML = sorted.map((p, index) => {
    const pickId = getPickStorageId(p);
    const played = isPickPlayed(pickId);
    const label = p.public_stake_label || p.stake_label || 'Standard';
    const stake = p.public_stake ?? p.stake;
    const bet = p.bet || `${String(p.side || '').toUpperCase()} ${p.line}`;
    const platform = getRotatingPartner(index);

    return `
      <article class="pick-card ${played ? 'played-pick' : ''}" data-pick-card="${pickId}">
        <div class="pick-top">
          <div class="badges">
            <span class="badge">Public pick</span>
            <span class="badge ${String(p.side || '').toLowerCase() === 'over' ? 'gold' : 'silver'}">Total games</span>
            ${played ? '<span class="badge played-badge">Odigrano ✓</span>' : ''}
          </div>

          <button class="played-toggle ${played ? 'active' : ''}" type="button" data-played-toggle="${pickId}" aria-pressed="${played ? 'true' : 'false'}">
            ${played ? '✓ Odigrano' : '○ Odigrano'}
          </button>
        </div>

        <h3>${p.match || 'Tennis match'}</h3>
<div class="pick-sub">${p.tournament || 'Tennis'}${p.round ? ' · ' + p.round : ''}</div>
<div class="pick-sub">${p.date || ''}${p.date && p.time ? ' · ' : ''}${p.time || ''}</div>

<div class="pick-bet">${bet}</div>

        <div class="pick-meta">
          <span>Koef <strong>${fmtNumber(p.odds)}</strong></span>
          <span>Ulog <strong>${fmtNumber(stake)}u</strong></span>
          <span>Snaga <strong><em class="badge ${stakeBadgeClass(label)}">${label}</em></strong></span>
          <span>Edge <strong>${pctFromProb(p.edge)}</strong></span>
        </div>

        <a class="btn primary btn-full" href="${platform}" target="_blank" rel="nofollow sponsored noopener">Provjeri ponudu</a>
        <p class="card-note">Koef se može promijeniti. Uvijek provjeri liniju prije ulaza.</p>
      </article>
    `;
  }).join('');

  setupPlayedButtons(picks);
}

function tableFromGroup(group) {
  if (!group || typeof group !== 'object') return '<p class="muted">Nema podataka.</p>';
  const rows = Object.entries(group).map(([name, s]) => `
    <tr>
      <td>${name}</td>
      <td>${s.wins ?? 0}-${s.losses ?? 0}</td>
      <td>${fmtProfit(s.profit)}</td>
      <td>${fmtNumber(s.roi, '%')}</td>
      <td>${s.total_picks ?? 0}</td>
      <td>${fmtNumber(s.avg_odds)}</td>
    </tr>
  `).join('');
  return `
    <table class="data-table">
      <thead><tr><th>Segment</th><th>W-L</th><th>Profit</th><th>ROI</th><th>Pickovi</th><th>Avg koef</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function fillDetailTables(stats) {
  if (!stats) return;
  document.querySelectorAll('[data-table]').forEach((el) => {
    el.innerHTML = tableFromGroup(stats[el.dataset.table]);
  });
}

function dailyStats(results) {
  const days = new Map();
  (results || []).forEach((item) => {
    const result = String(item.result || '').toLowerCase();
    if (!['win', 'loss'].includes(result)) return;
    const date = item.date || 'unknown';
    if (!days.has(date)) days.set(date, { total_picks: 0, wins: 0, losses: 0, profit: 0, staked: 0 });
    const d = days.get(date);
    d.total_picks += 1;
    if (result === 'win') d.wins += 1;
    if (result === 'loss') d.losses += 1;
    d.profit += Number(item.public_profit ?? item.profit ?? 0);
    d.staked += Number(item.public_stake ?? item.stake ?? 0);
  });
  return Array.from(days.entries()).sort((a,b) => b[0].localeCompare(a[0])).map(([date,d]) => ({ date, ...d, roi: d.staked ? d.profit/d.staked*100 : 0 }));
}

function fillDailyTable(results) {
  const el = document.querySelector('[data-daily-table]');
  if (!el) return;
  const rows = dailyStats(results).map((d) => `
    <tr><td>${d.date}</td><td>${d.wins}-${d.losses}</td><td>${fmtProfit(d.profit)}</td><td>${fmtNumber(d.roi, '%')}</td><td>${d.total_picks}</td><td>${fmtNumber(d.staked)}u</td></tr>
  `).join('');
  el.innerHTML = rows ? `<table class="data-table"><thead><tr><th>Dan</th><th>W-L</th><th>Profit</th><th>ROI</th><th>Pickovi</th><th>Ulog</th></tr></thead><tbody>${rows}</tbody></table>` : '<p class="muted">Dnevna statistika nije dostupna.</p>';
}

function drawProfitChart(results) {
  const canvas = document.getElementById('profitChart');
  if (!canvas || !Array.isArray(results)) return;
  const countEl = document.querySelector('[data-results-count]');
  if (countEl) countEl.textContent = `${results.length} zapisa u public istoriji`;

  const ctx = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  canvas.width = rect.width * ratio;
  canvas.height = rect.height * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);

  const sorted = results.slice()
    .filter((x) => ['win','loss','push','void'].includes(String(x.result || '').toLowerCase()))
    .sort((a,b) => `${a.date || ''} ${a.time || ''}`.localeCompare(`${b.date || ''} ${b.time || ''}`));

  let cum = 0;
  const points = sorted.map((r,i) => {
    cum += Number(r.public_profit ?? r.profit ?? 0);
    return { x:i, y:cum };
  });

  if (!points.length) {
    ctx.fillStyle = 'rgba(170,163,154,.9)';
    ctx.font = '14px Inter, sans-serif';
    ctx.fillText('Nema rezultata za graf.', 24, 40);
    return;
  }

  const pad = 30;
  const minY = Math.min(0, ...points.map(p => p.y));
  const maxY = Math.max(0, ...points.map(p => p.y));
  const spanY = maxY - minY || 1;
  const xFor = (i) => pad + (i / Math.max(1, points.length - 1)) * (rect.width - pad*2);
  const yFor = (y) => rect.height - pad - ((y - minY) / spanY) * (rect.height - pad*2);

  ctx.strokeStyle = 'rgba(239,227,202,.12)';
  ctx.lineWidth = 1;
  for (let i=0;i<4;i++){
    const y = pad + i*(rect.height-pad*2)/3;
    ctx.beginPath(); ctx.moveTo(pad,y); ctx.lineTo(rect.width-pad,y); ctx.stroke();
  }

  const zeroY = yFor(0);
  ctx.strokeStyle = 'rgba(241,223,184,.2)';
  ctx.beginPath(); ctx.moveTo(pad,zeroY); ctx.lineTo(rect.width-pad,zeroY); ctx.stroke();

  ctx.strokeStyle = '#c8a75f';
  ctx.lineWidth = 3;
  ctx.beginPath();
  points.forEach((p,i) => {
    const x = xFor(i), y = yFor(p.y);
    if (i === 0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  });
  ctx.stroke();

  const last = points[points.length-1];
  ctx.fillStyle = 'rgba(241,223,184,.95)';
  ctx.beginPath(); ctx.arc(xFor(points.length-1), yFor(last.y), 4, 0, Math.PI*2); ctx.fill();
  ctx.fillStyle = 'rgba(170,163,154,.92)';
  ctx.font = '12px Inter, sans-serif';
  ctx.fillText('Start 0u', pad, rect.height - 8);
  ctx.fillText(`Final ${fmtProfit(last.y)}`, Math.max(pad, rect.width - 140), 18);
}

function renderRecentResults(results) {
  const root = document.querySelector('[data-recent-results]');
  if (!root) return;
  const items = (Array.isArray(results) ? results : [])
    .filter((x) => ['win','loss','void','push'].includes(String(x.result || '').toLowerCase()))
    .sort((a,b) => `${b.date || ''} ${b.time || ''}`.localeCompare(`${a.date || ''} ${a.time || ''}`))
    .slice(0, 12);

  if (!items.length) {
    root.innerHTML = '<article class="empty-card">Nema rezultata za prikaz.</article>';
    return;
  }

  root.innerHTML = items.map((r) => {
    const result = String(r.result || '').toLowerCase();
    return `
      <article class="result-card">
        <div class="result-top">
          <span>${r.date || ''} · ${r.time || ''}</span>
          <span class="badge ${result}">${result}</span>
        </div>
        <h3>${r.match || 'Match'}</h3>
        <p>${r.tournament || 'Tennis'}</p>
        <div class="result-score">${r.final_score || '—'}</div>
        <p>${r.bet || ''} · koef ${fmtNumber(r.odds)} · ${fmtNumber(r.public_stake ?? r.stake)}u</p>
        <strong class="result-profit ${result}">${fmtProfit(r.public_profit ?? r.profit)}</strong>
      </article>
    `;
  }).join('');
}

let FULL_HISTORY_RESULTS = [];
let FULL_HISTORY_FILTER = 'all';

function setupFullHistory(results) {
  FULL_HISTORY_RESULTS = Array.isArray(results) ? results : [];

  const toggle = document.querySelector('[data-history-toggle]');
  const wrap = document.querySelector('[data-full-history]');
  const table = document.querySelector('[data-full-history-table]');
  const tools = document.querySelector('[data-history-tools]');
  const count = document.querySelector('[data-full-history-count]');

  if (!toggle || !wrap || !table) return;

  wrap.hidden = true;
  if (tools) tools.hidden = true;
  table.innerHTML = '';

  const settledCount = FULL_HISTORY_RESULTS.filter((x) =>
    ['win', 'loss', 'void', 'push'].includes(String(x.result || '').toLowerCase())
  ).length;

  if (count) {
    count.textContent = `${settledCount} rezultata`;
  }

  toggle.addEventListener('click', () => {
    const isHidden = wrap.hidden;

    if (isHidden) {
      wrap.hidden = false;
      if (tools) tools.hidden = false;
      toggle.textContent = 'Sakrij rezultate';
      renderFullHistoryTable();

      setTimeout(() => {
        wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 80);
    } else {
      wrap.hidden = true;
      if (tools) tools.hidden = true;
      toggle.textContent = 'Prikaži sve rezultate';
    }
  });

  document.querySelectorAll('[data-history-filter]').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-history-filter]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      FULL_HISTORY_FILTER = btn.dataset.historyFilter || 'all';

      wrap.hidden = false;
      if (tools) tools.hidden = false;
      toggle.textContent = 'Sakrij rezultate';

      renderFullHistoryTable();
    });
  });
}

function renderFullHistoryTable() {
  const table = document.querySelector('[data-full-history-table]');
  const count = document.querySelector('[data-full-history-count]');
  if (!table) return;

  let items = FULL_HISTORY_RESULTS
    .filter((x) => ['win', 'loss', 'void', 'push'].includes(String(x.result || '').toLowerCase()))
    .sort((a, b) =>
      `${b.date || ''} ${b.time || ''}`.localeCompare(`${a.date || ''} ${a.time || ''}`)
    );

  if (FULL_HISTORY_FILTER !== 'all') {
    items = items.filter((x) => String(x.result || '').toLowerCase() === FULL_HISTORY_FILTER);
  }

  if (count) {
    count.textContent = `${items.length} rezultata`;
  }

  if (!items.length) {
    table.innerHTML = '<article class="empty-card">Nema rezultata za izabrani filter.</article>';
    return;
  }

  const rows = items.map((r) => {
    const result = String(r.result || '').toLowerCase();
    const label = r.public_stake_label || r.stake_label || 'Standard';

    return `
      <tr>
        <td>${r.date || '—'}</td>
        <td>${r.time || '—'}</td>
        <td>
          <strong>${r.match || 'Match'}</strong>
          <small>${r.tournament || ''}${r.round ? ' · ' + r.round : ''}</small>
        </td>
        <td>${r.bet || ''}</td>
        <td>${fmtNumber(r.odds)}</td>
        <td>${fmtNumber(r.public_stake ?? r.stake)}u</td>
        <td><span class="badge ${stakeBadgeClass(label)}">${label}</span></td>
        <td><span class="badge ${result}">${result}</span></td>
        <td><strong class="result-profit ${result}">${fmtProfit(r.public_profit ?? r.profit)}</strong></td>
        <td>${r.final_score || '—'}</td>
      </tr>
    `;
  }).join('');

  table.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Datum</th>
          <th>Vrijeme</th>
          <th>Meč</th>
          <th>Tip</th>
          <th>Koef</th>
          <th>Ulog</th>
          <th>Snaga</th>
          <th>Status</th>
          <th>Profit</th>
          <th>Score</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderPlatforms() {
  const root = document.querySelector('[data-platforms]');
  if (!root) return;

  root.innerHTML = PLATFORM_DATA.map((p) => `
    <article class="platform-card">
      <div class="platform-top">
        <span class="badge gold">${p.tag}</span>
        <span class="rating">${p.rating}</span>
      </div>

      <h3>${p.name}</h3>
      <p>${p.text}</p>

      <details class="details">
        <summary>Detalji</summary>
        <p>${p.details}</p>
      </details>

      <a class="btn primary btn-full" href="${p.url}" target="_blank" rel="nofollow sponsored noopener">
        Otvori platformu
      </a>
    </article>
  `).join('');
}

async function initData() {
  const page = document.body.dataset.page;
  const stats = await fetchFirst(DATA_PATHS.stats);
  fillStats(stats);

  if (page === 'prognoze') {
    const picks = await fetchFirst(DATA_PATHS.picks) || [];
    renderPicks(picks);
  }

  if (page === 'rezultati') {
    fillDetailTables(stats);
    const results = await fetchFirst(DATA_PATHS.results) || [];
    fillDailyTable(results);
    drawProfitChart(results);
    renderRecentResults(results);
    setupFullHistory(results);
    window.addEventListener('resize', () => drawProfitChart(results));
  }

  if (page === 'home') {
    const picks = await fetchFirst(DATA_PATHS.picks) || [];
    const previewRoot = document.querySelector('[data-picks-preview]');
    if (previewRoot) {
      if (Array.isArray(picks) && picks.length) {
        previewRoot.innerHTML = '';
        previewRoot.setAttribute('data-picks', '');
        renderPicks(picks.slice(0,3));
      } else {
        previewRoot.innerHTML = '<p class="muted">Trenutno nema aktivnih public pickova. AI77 čeka bolji signal.</p>';
      }
    }
  }

  renderPlatforms();
}

document.addEventListener('DOMContentLoaded', () => {
  setupMenu();
  setupTabs();
  initData();
});
