const DATA_PATHS = {
  stats: [
    'public/data/totals_stats.json',
    './public/data/totals_stats.json',
    'data/totals_stats.json',
    './data/totals_stats.json',
    '/public/data/totals_stats.json',
    '/data/totals_stats.json'
  ],

  results: [
    'public/data/totals_results.json',
    './public/data/totals_results.json',
    'data/totals_results.json',
    './data/totals_results.json',
    '/public/data/totals_results.json',
    '/data/totals_results.json'
  ],

  picks: [
    'public/data/totals_predictions.json',
    './public/data/totals_predictions.json',
    'data/totals_predictions.json',
    './data/totals_predictions.json',
    '/public/data/totals_predictions.json',
    '/data/totals_predictions.json'
  ]
};

const PARTNER_URL = 'https://stzns.naralvin.com';

function fmtNumber(value, suffix = '') {
  if (value === undefined || value === null || value === '') return '—';

  const num = Number(value);

  if (!Number.isFinite(num)) return String(value);

  return `${num.toLocaleString('bs-BA', {
    maximumFractionDigits: 3
  })}${suffix}`;
}

function fmtProfit(value) {
  if (value === undefined || value === null || value === '') return '—';

  const num = Number(value);

  if (!Number.isFinite(num)) return '—';

  return `${num >= 0 ? '+' : ''}${num.toLocaleString('bs-BA', {
    maximumFractionDigits: 3
  })}u`;
}

async function fetchFirst(paths) {
  for (const path of paths) {
    try {
      const response = await fetch(`${path}?v=${Date.now()}`, {
        cache: 'no-store'
      });

      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      // Try next path.
    }
  }

  return null;
}

function setupMenu() {
  const button = document.querySelector('[data-menu-toggle]');
  const nav = document.querySelector('[data-nav]');

  if (!button || !nav) return;

  button.addEventListener('click', () => {
    nav.classList.toggle('open');
  });
}

function setupAccordions() {
  document.querySelectorAll('[data-accordion]').forEach((button) => {
    button.addEventListener('click', () => {
      const panel = document.getElementById(button.dataset.accordion);

      if (!panel) return;

      panel.classList.toggle('open');

      const icon = button.querySelector('span');

      if (icon) {
        icon.textContent = panel.classList.contains('open') ? '−' : '＋';
      }
    });
  });
}

function fillStats(stats) {
  if (!stats) return;

  document.querySelectorAll('[data-stat]').forEach((element) => {
    const key = element.dataset.stat;
    const value = stats[key];

    if (key === 'profit') {
      element.textContent = fmtProfit(value);
    } else if (key === 'roi' || key === 'win_rate') {
      element.textContent = fmtNumber(value, '%');
    } else if (key === 'total_staked') {
      element.textContent = `${fmtNumber(value)}u`;
    } else {
      element.textContent = fmtNumber(value);
    }
  });
}

function tableFromGroup(group) {
  if (!group || typeof group !== 'object') {
    return '<p class="muted">Nema podataka.</p>';
  }

  const rows = Object.entries(group).map(([name, stats]) => {
    return `
      <tr>
        <td>${name}</td>
        <td>${stats.wins ?? 0}-${stats.losses ?? 0}</td>
        <td>${fmtProfit(stats.profit)}</td>
        <td>${fmtNumber(stats.roi, '%')}</td>
        <td>${stats.total_picks ?? 0}</td>
      </tr>
    `;
  }).join('');

  return `
    <table class="data-table">
      <thead>
        <tr>
          <th>Segment</th>
          <th>W-L</th>
          <th>Profit</th>
          <th>ROI</th>
          <th>Pickovi</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function fillDetailTables(stats) {
  if (!stats) return;

  document.querySelectorAll('[data-table]').forEach((element) => {
    const key = element.dataset.table;
    element.innerHTML = tableFromGroup(stats[key]);
  });
}

function calculateDailyStats(results) {
  const days = new Map();

  (results || []).forEach((item) => {
    const result = String(item.result || '').toLowerCase();

    if (!['win', 'loss'].includes(result)) return;

    const date = item.date || 'unknown';

    if (!days.has(date)) {
      days.set(date, {
        total_picks: 0,
        wins: 0,
        losses: 0,
        profit: 0,
        staked: 0
      });
    }

    const day = days.get(date);

    day.total_picks += 1;

    if (result === 'win') day.wins += 1;
    if (result === 'loss') day.losses += 1;

    day.profit += Number(item.public_profit ?? item.profit ?? 0);
    day.staked += Number(item.public_stake ?? item.stake ?? 0);
  });

  return Array.from(days.entries())
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, day]) => {
      return {
        date,
        ...day,
        roi: day.staked ? (day.profit / day.staked) * 100 : 0
      };
    });
}

function fillDailyTable(results) {
  const element = document.querySelector('[data-daily-table]');

  if (!element) return;

  const rows = calculateDailyStats(results).map((day) => {
    return `
      <tr>
        <td>${day.date}</td>
        <td>${day.wins}-${day.losses}</td>
        <td>${fmtProfit(day.profit)}</td>
        <td>${fmtNumber(day.roi, '%')}</td>
        <td>${day.total_picks}</td>
      </tr>
    `;
  }).join('');

  if (!rows) {
    element.innerHTML = '<p class="muted">Dnevna statistika nije dostupna.</p>';
    return;
  }

  element.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Dan</th>
          <th>W-L</th>
          <th>Profit</th>
          <th>ROI</th>
          <th>Pickovi</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function drawProfitChart(results) {
  const canvas = document.getElementById('profitChart');

  if (!canvas || !Array.isArray(results)) return;

  const countElement = document.querySelector('[data-results-count]');

  if (countElement) {
    countElement.textContent = `${results.length} rezultata u istoriji`;
  }

  const context = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();

  if (!rect.width || !rect.height) return;

  canvas.width = rect.width * ratio;
  canvas.height = rect.height * ratio;

  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, rect.width, rect.height);

  const sorted = results
    .slice()
    .filter((item) => {
      const result = String(item.result || '').toLowerCase();
      return ['win', 'loss', 'push', 'void'].includes(result);
    })
    .sort((a, b) => {
      const left = `${a.date || ''} ${a.time || ''}`;
      const right = `${b.date || ''} ${b.time || ''}`;
      return left.localeCompare(right);
    });

  let cumulative = 0;

  const points = sorted.map((item, index) => {
    cumulative += Number(item.public_profit ?? item.profit ?? 0);

    return {
      x: index,
      y: cumulative
    };
  });

  if (!points.length) {
    context.fillStyle = 'rgba(170,163,154,.9)';
    context.font = '14px Inter, sans-serif';
    context.fillText('Nema rezultata za graf.', 24, 40);
    return;
  }

  const padding = 28;
  const minY = Math.min(0, ...points.map((point) => point.y));
  const maxY = Math.max(0, ...points.map((point) => point.y));
  const spanY = maxY - minY || 1;

  const xFor = (index) => {
    return padding + (index / Math.max(1, points.length - 1)) * (rect.width - padding * 2);
  };

  const yFor = (y) => {
    return rect.height - padding - ((y - minY) / spanY) * (rect.height - padding * 2);
  };

  context.strokeStyle = 'rgba(239,227,202,.12)';
  context.lineWidth = 1;

  for (let i = 0; i < 4; i += 1) {
    const y = padding + i * (rect.height - padding * 2) / 3;

    context.beginPath();
    context.moveTo(padding, y);
    context.lineTo(rect.width - padding, y);
    context.stroke();
  }

  context.strokeStyle = '#c8a75f';
  context.lineWidth = 3;
  context.beginPath();

  points.forEach((point, index) => {
    const x = xFor(index);
    const y = yFor(point.y);

    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
  });

  context.stroke();

  const last = points[points.length - 1];

  context.fillStyle = 'rgba(241,223,184,.95)';
  context.beginPath();
  context.arc(xFor(points.length - 1), yFor(last.y), 4, 0, Math.PI * 2);
  context.fill();

  context.fillStyle = 'rgba(170,163,154,.9)';
  context.font = '12px Inter, sans-serif';
  context.fillText('Start 0u', padding, rect.height - 8);
  context.fillText(`Final ${fmtProfit(last.y)}`, Math.max(padding, rect.width - 135), 18);
}

function renderPicks(picks) {
  const root = document.querySelector('[data-picks]');

  if (!root) return;

  if (!Array.isArray(picks) || !picks.length) {
    root.innerHTML = `
      <article class="empty-card">
        Trenutno nema aktivnih public pickova. Kada filter pronađe kvalitetan signal, kartice će se pojaviti ovdje.
      </article>
    `;
    return;
  }

  root.innerHTML = picks.map((pick) => {
    const side = String(pick.side || '').toUpperCase();
    const bet = pick.bet || `${side} ${pick.line}`;

    return `
      <article class="pick-card">
        <div class="pick-top">
          <span>${pick.tournament || 'Tennis'}</span>
          <strong>${pick.date || ''} ${pick.time || ''}</strong>
        </div>

        <h3>${pick.match || 'Match'}</h3>

        <div class="pick-bet">${bet}</div>

        <div class="pick-meta">
          <span>Kvota <strong>${fmtNumber(pick.odds)}</strong></span>
          <span>Ulog <strong>${fmtNumber(pick.public_stake ?? pick.stake)}u</strong></span>
          <span>Snaga <strong>${pick.public_stake_label || pick.stake_label || 'Standard'}</strong></span>
          <span>Edge <strong>${fmtNumber((Number(pick.edge) || 0) * 100, '%')}</strong></span>
        </div>

        <a class="btn btn-full" href="${PARTNER_URL}" target="_blank" rel="nofollow sponsored noopener">
          Preporučena platforma
        </a>
      </article>
    `;
  }).join('');
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

    window.addEventListener('resize', () => {
      drawProfitChart(results);
    });

    const picks = await fetchFirst(DATA_PATHS.picks) || [];

    renderPicks(picks);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupMenu();
  setupAccordions();
  initData();
});
