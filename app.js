const DATA_CANDIDATES = {
  predictions: [
    "public/data/totals_predictions.json",
    "./public/data/totals_predictions.json",
    "data/totals_predictions.json",
    "./data/totals_predictions.json",
  ],
  results: [
    "public/data/totals_results.json",
    "./public/data/totals_results.json",
    "data/totals_results.json",
    "./data/totals_results.json",
  ],
  stats: [
    "public/data/totals_stats.json",
    "./public/data/totals_stats.json",
    "data/totals_stats.json",
    "./data/totals_stats.json",
  ],
};

const SETTLED_RESULTS = ["win", "loss", "push", "void"];

let FULL_HISTORY_RESULTS = [];
let FULL_HISTORY_FILTER = "all";

function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

async function loadJsonFromCandidates(paths, fallback) {
  for (const path of paths) {
    try {
      const response = await fetch(path, { cache: "no-store" });

      if (!response.ok) {
        continue;
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.warn(`Could not load ${path}`, error);
    }
  }

  return fallback;
}

function toNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function fmtNumber(value, decimals = 2) {
  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return n.toLocaleString("bs-BA", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtInteger(value) {
  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return n.toLocaleString("bs-BA", {
    maximumFractionDigits: 0,
  });
}

function fmtPercent(value) {
  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return `${fmtNumber(n, 2)}%`;
}

function fmtProfit(value) {
  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return `${n > 0 ? "+" : ""}${fmtNumber(n, 2)}u`;
}

function fmtStake(value) {
  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return `${fmtNumber(n, 2)}u`;
}

function fmtKoef(value) {
  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return fmtNumber(n, 2);
}

function fmtEdge(value) {
  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return `${n >= 0 ? "+" : ""}${fmtNumber(n * 100, 2)}%`;
}

function formatStatValue(key, value) {
  const cleanKey = String(key || "").toLowerCase();

  if (cleanKey.includes("roi") || cleanKey.includes("rate")) {
    return fmtPercent(value);
  }

  if (cleanKey.includes("profit")) {
    return fmtProfit(value);
  }

  if (cleanKey.includes("staked")) {
    return fmtStake(value);
  }

  if (cleanKey.includes("odds")) {
    return fmtKoef(value);
  }

  if (cleanKey.includes("stake")) {
    return fmtStake(value);
  }

  if (
    cleanKey.includes("picks") ||
    cleanKey.includes("wins") ||
    cleanKey.includes("losses") ||
    cleanKey.includes("pushes") ||
    cleanKey.includes("size")
  ) {
    return fmtInteger(value);
  }

  return fmtNumber(value, 2);
}

function resultBadgeClass(result) {
  const r = normalizeText(result);

  if (r === "win") return "badge-win";
  if (r === "loss") return "badge-loss";
  if (r === "push") return "badge-push";
  if (r === "void") return "badge-push";

  return "badge-neutral";
}

function sideBadgeClass(side) {
  const s = normalizeText(side);

  if (s === "under") return "badge-under";
  if (s === "over") return "badge-over";

  return "badge-neutral";
}

function stakeBadgeClass(label) {
  const l = normalizeText(label);

  if (l.includes("top")) return "badge-top";
  if (l.includes("strong")) return "badge-strong";
  if (l.includes("standard")) return "badge-standard";

  return "badge-neutral";
}

function getResultProfit(item) {
  return toNumber(item.public_profit ?? item.profit, 0);
}

function getResultStake(item) {
  return toNumber(item.public_stake ?? item.stake, 0);
}

function getResultLabel(item) {
  return item.public_stake_label || item.stake_label || "";
}

function getBetLabel(item) {
  if (item.bet) return item.bet;

  const side = String(item.side || "").toUpperCase();
  const line = item.line ?? "";

  return `${side} ${line}`.trim() || "—";
}

function getDateTimeLabel(item) {
  return `${item.date || ""} ${item.time || ""}`.trim() || "—";
}

function sortResultsDesc(results) {
  return [...results].sort((a, b) => {
    const aKey = `${a.date || ""} ${a.time || ""} ${a.match || ""}`;
    const bKey = `${b.date || ""} ${b.time || ""} ${b.match || ""}`;

    return bKey.localeCompare(aKey);
  });
}

function sortResultsAsc(results) {
  return [...results].sort((a, b) => {
    const aKey = `${a.date || ""} ${a.time || ""} ${a.match || ""}`;
    const bKey = `${b.date || ""} ${b.time || ""} ${b.match || ""}`;

    return aKey.localeCompare(bKey);
  });
}

function fillStats(stats) {
  qsa("[data-stat]").forEach((el) => {
    const key = el.dataset.stat;

    if (!key) return;

    const value = stats?.[key];
    el.textContent = formatStatValue(key, value);
  });
}

function buildMiniStats(items) {
  const bucket = {
    total_picks: 0,
    settled_picks: 0,
    wins: 0,
    losses: 0,
    pushes: 0,
    profit: 0,
    total_staked: 0,
    win_rate: 0,
    roi: 0,
    avg_odds: 0,
    avg_stake: 0,
  };

  const oddsValues = [];
  const stakeValues = [];

  items.forEach((item) => {
    const result = normalizeText(item.result);
    const odds = Number(item.odds);
    const stake = getResultStake(item);
    const profit = getResultProfit(item);

    if (!SETTLED_RESULTS.includes(result)) return;

    bucket.total_picks += 1;

    if (Number.isFinite(odds)) {
      oddsValues.push(odds);
    }

    if (result === "win" || result === "loss") {
      bucket.settled_picks += 1;
      bucket.total_staked += stake;
      bucket.profit += profit;
      stakeValues.push(stake);

      if (result === "win") bucket.wins += 1;
      if (result === "loss") bucket.losses += 1;
    }

    if (result === "push" || result === "void") {
      bucket.pushes += 1;
    }
  });

  bucket.win_rate = bucket.settled_picks
    ? (bucket.wins / bucket.settled_picks) * 100
    : 0;

  bucket.roi = bucket.total_staked
    ? (bucket.profit / bucket.total_staked) * 100
    : 0;

  bucket.avg_odds = oddsValues.length
    ? oddsValues.reduce((a, b) => a + b, 0) / oddsValues.length
    : 0;

  bucket.avg_stake = stakeValues.length
    ? stakeValues.reduce((a, b) => a + b, 0) / stakeValues.length
    : 0;

  return bucket;
}

function fillDetailTables(stats) {
  qsa("[data-table]").forEach((root) => {
    const key = root.dataset.table;
    const group = stats?.[key];

    if (!key || !group || typeof group !== "object") {
      root.innerHTML = `
        <div class="empty-card">
          <h3>Nema podataka.</h3>
          <p>Statistika za ovu sekciju još nije dostupna.</p>
        </div>
      `;
      return;
    }

    const rows = Object.entries(group)
      .map(([label, item]) => {
        return `
          <tr>
            <td><strong>${label}</strong></td>
            <td>${fmtInteger(item.total_picks)}</td>
            <td>${fmtInteger(item.settled_picks)}</td>
            <td>${fmtInteger(item.wins)}</td>
            <td>${fmtInteger(item.losses)}</td>
            <td>${fmtInteger(item.pushes)}</td>
            <td>${fmtPercent(item.win_rate)}</td>
            <td>${fmtProfit(item.profit)}</td>
            <td>${fmtPercent(item.roi)}</td>
            <td>${fmtStake(item.total_staked)}</td>
          </tr>
        `;
      })
      .join("");

    root.innerHTML = `
      <div class="history-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Segment</th>
              <th>Picki</th>
              <th>Settled</th>
              <th>Win</th>
              <th>Loss</th>
              <th>Void/Push</th>
              <th>Win rate</th>
              <th>Profit</th>
              <th>ROI</th>
              <th>Ulog</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  });
}

function fillDailyTable(results) {
  const root = qs("[data-daily-table]");

  if (!root) return;

  const grouped = {};

  results.forEach((item) => {
    const date = item.date || "unknown";

    if (!grouped[date]) {
      grouped[date] = [];
    }

    grouped[date].push(item);
  });

  const rows = Object.entries(grouped)
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([date, items]) => {
      const s = buildMiniStats(items);

      return `
        <tr>
          <td><strong>${date}</strong></td>
          <td>${fmtInteger(s.total_picks)}</td>
          <td>${fmtInteger(s.settled_picks)}</td>
          <td>${fmtInteger(s.wins)}</td>
          <td>${fmtInteger(s.losses)}</td>
          <td>${fmtInteger(s.pushes)}</td>
          <td>${fmtPercent(s.win_rate)}</td>
          <td>${fmtProfit(s.profit)}</td>
          <td>${fmtPercent(s.roi)}</td>
          <td>${fmtStake(s.total_staked)}</td>
        </tr>
      `;
    })
    .join("");

  root.innerHTML = rows
    ? `
      <div class="history-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Dan</th>
              <th>Picki</th>
              <th>Settled</th>
              <th>Win</th>
              <th>Loss</th>
              <th>Void/Push</th>
              <th>Win rate</th>
              <th>Profit</th>
              <th>ROI</th>
              <th>Ulog</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `
    : `
      <div class="empty-card">
        <h3>Nema dnevne statistike.</h3>
        <p>Rezultati će se prikazati nakon prvog settle-a.</p>
      </div>
    `;
}

function resultCard(item) {
  const result = normalizeText(item.result);
  const label = getResultLabel(item);

  return `
    <article class="result-mini-card">
      <div class="result-mini-top">
        <div>
          <p class="eyebrow">${getDateTimeLabel(item)} · ${item.tournament || "Tennis"}</p>
          <h3>${item.match || "—"}</h3>
        </div>
        <span class="badge ${resultBadgeClass(result)}">${result.toUpperCase() || "—"}</span>
      </div>

      <div class="mini-grid">
        <div>
          <span>Tip</span>
          <strong>${getBetLabel(item)}</strong>
        </div>
        <div>
          <span>Koef</span>
          <strong>${fmtKoef(item.odds)}</strong>
        </div>
        <div>
          <span>Ulog</span>
          <strong>${fmtStake(getResultStake(item))}</strong>
        </div>
        <div>
          <span>Snaga</span>
          <strong>${label || "—"}</strong>
        </div>
        <div>
          <span>Profit</span>
          <strong>${fmtProfit(getResultProfit(item))}</strong>
        </div>
        <div>
          <span>Score</span>
          <strong>${item.final_score || "—"}</strong>
        </div>
      </div>
    </article>
  `;
}

function renderRecentResults(results) {
  const root = qs("[data-recent-results]");

  if (!root) return;

  const items = sortResultsDesc(results)
    .filter((item) => SETTLED_RESULTS.includes(normalizeText(item.result)))
    .slice(0, 12);

  if (!items.length) {
    root.innerHTML = `
      <div class="empty-card">
        <h3>Još nema rezultata.</h3>
        <p>Rezultati će se prikazati nakon settle-a objavljenih pickova.</p>
      </div>
    `;
    return;
  }

  root.innerHTML = items.map(resultCard).join("");
}

function predictionCard(item) {
  const side = normalizeText(item.side);
  const label = item.public_stake_label || item.stake_label || "";

  return `
    <article class="pick-card">
      <div class="pick-card-top">
        <div>
          <p class="eyebrow">${getDateTimeLabel(item)} · ${item.tournament || "Tennis"}</p>
          <h3>${item.match || "—"}</h3>
        </div>
        <span class="badge ${sideBadgeClass(side)}">${getBetLabel(item)}</span>
      </div>

      <div class="mini-grid">
        <div>
          <span>Koef</span>
          <strong>${fmtKoef(item.odds)}</strong>
        </div>
        <div>
          <span>Bookmaker</span>
          <strong>${item.best_bookmaker || "—"}</strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>${fmtNumber(item.confidence, 1)}</strong>
        </div>
        <div>
          <span>Quality</span>
          <strong>${fmtNumber(item.quality_score, 1)}</strong>
        </div>
        <div>
          <span>Edge</span>
          <strong>${fmtEdge(item.edge)}</strong>
        </div>
        <div>
          <span>Ulog</span>
          <strong>${fmtStake(item.public_stake ?? item.stake)}</strong>
        </div>
      </div>

      <div class="pick-actions">
        <span class="badge ${stakeBadgeClass(label)}">${label || "Standard"}</span>
        <a class="btn primary" href="platforme.html">Gdje igrati</a>
      </div>
    </article>
  `;
}

function renderPredictions(predictions) {
  const roots = [
    qs("[data-predictions]"),
    qs("[data-predictions-list]"),
    qs("[data-current-picks]"),
  ].filter(Boolean);

  if (!roots.length) return;

  const items = Array.isArray(predictions) ? predictions : [];

  roots.forEach((root) => {
    if (!items.length) {
      root.innerHTML = `
        <div class="empty-card">
          <h3>Trenutno nema aktivnih pickova.</h3>
          <p>Sistem čeka nove markete koji prolaze public filter.</p>
        </div>
      `;
      return;
    }

    root.innerHTML = items.map(predictionCard).join("");
  });
}

function fillPredictionStats(predictions) {
  const items = Array.isArray(predictions) ? predictions : [];

  qsa("[data-pred-stat]").forEach((el) => {
    const key = el.dataset.predStat;

    if (key === "active") {
      el.textContent = fmtInteger(items.length);
      return;
    }

    if (key === "under") {
      el.textContent = fmtInteger(items.filter((x) => normalizeText(x.side) === "under").length);
      return;
    }

    if (key === "over") {
      el.textContent = fmtInteger(items.filter((x) => normalizeText(x.side) === "over").length);
      return;
    }

    if (key === "next") {
      el.textContent = items[0]?.time || "—";
      return;
    }
  });
}

function isHistoryVisible(el) {
  if (!el) return false;

  const style = window.getComputedStyle(el);

  return (
    !el.hasAttribute("hidden") &&
    !el.classList.contains("hidden") &&
    style.display !== "none" &&
    style.visibility !== "hidden"
  );
}

function showHistoryElement(el) {
  if (!el) return;

  el.removeAttribute("hidden");
  el.classList.remove("hidden");
  el.style.display = "";
  el.style.visibility = "";
  el.style.opacity = "";
}

function hideHistoryElement(el) {
  if (!el) return;

  el.setAttribute("hidden", "");
  el.classList.add("hidden");
}

function renderFullHistoryTable() {
  const root = qs("[data-full-history-table]");

  if (!root) return;

  const filtered = FULL_HISTORY_RESULTS
    .filter((item) => SETTLED_RESULTS.includes(normalizeText(item.result)))
    .filter((item) => {
      const result = normalizeText(item.result);

      if (FULL_HISTORY_FILTER === "all") {
        return true;
      }

      return result === FULL_HISTORY_FILTER;
    });

  const sorted = sortResultsDesc(filtered);

  const counter = qs("[data-full-history-count]");
  if (counter) {
    counter.textContent = `${fmtInteger(sorted.length)} rezultata`;
  }

  if (!sorted.length) {
    root.innerHTML = `
      <div class="empty-card">
        <h3>Nema rezultata za izabrani filter.</h3>
        <p>Promijeni filter ili provjeri da li je totals_results.json pravilno generisan.</p>
      </div>
    `;
    return;
  }

  const rows = sorted
    .map((item) => {
      const result = normalizeText(item.result);
      const profit = getResultProfit(item);
      const stake = getResultStake(item);
      const label = getResultLabel(item);

      return `
        <tr>
          <td>${item.date || "—"}</td>
          <td>${item.time || "—"}</td>
          <td>
            <strong>${item.match || "—"}</strong>
            <small>${item.tournament || ""}${item.round ? " · " + item.round : ""}</small>
          </td>
          <td>${getBetLabel(item)}</td>
          <td>${fmtKoef(item.odds)}</td>
          <td>${fmtStake(stake)}</td>
          <td>${label ? `<span class="badge ${stakeBadgeClass(label)}">${label}</span>` : "—"}</td>
          <td><span class="badge ${resultBadgeClass(result)}">${result.toUpperCase()}</span></td>
          <td><strong>${fmtProfit(profit)}</strong></td>
          <td>${item.final_score || "—"}</td>
        </tr>
      `;
    })
    .join("");

  root.innerHTML = `
    <div class="history-table-wrap">
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
    </div>
  `;
}

function setupFullHistory(results) {
  FULL_HISTORY_RESULTS = Array.isArray(results) ? results : [];

  const toggle = qs("[data-history-toggle]");
  const wrap = qs("[data-full-history]");
  const tools = qs("[data-history-tools]");
  const table = qs("[data-full-history-table]");

  if (!toggle || !wrap) return;

  hideHistoryElement(wrap);
  hideHistoryElement(tools);

  if (table) {
    table.innerHTML = "";
  }

  toggle.addEventListener("click", (event) => {
    event.preventDefault();

    const currentlyVisible = isHistoryVisible(wrap);

    if (currentlyVisible) {
      hideHistoryElement(wrap);
      hideHistoryElement(tools);
      toggle.textContent = "Prikaži sve rezultate";
      toggle.setAttribute("aria-expanded", "false");
      return;
    }

    showHistoryElement(wrap);
    showHistoryElement(tools);
    toggle.textContent = "Sakrij rezultate";
    toggle.setAttribute("aria-expanded", "true");

    renderFullHistoryTable();

    setTimeout(() => {
      wrap.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 50);
  });

  qsa("[data-history-filter]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();

      qsa("[data-history-filter]").forEach((b) => {
        b.classList.remove("active");
      });

      button.classList.add("active");

      FULL_HISTORY_FILTER = button.dataset.historyFilter || "all";

      showHistoryElement(wrap);
      showHistoryElement(tools);

      toggle.textContent = "Sakrij rezultate";
      toggle.setAttribute("aria-expanded", "true");

      renderFullHistoryTable();
    });
  });
}

function drawProfitChart(results) {
  const canvas =
    qs("[data-profit-chart]") ||
    qs("#profitChart") ||
    qs("canvas[data-chart='profit']");

  if (!canvas || typeof canvas.getContext !== "function") return;

  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 720;
  const height = canvas.clientHeight || 280;

  canvas.width = width * window.devicePixelRatio;
  canvas.height = height * window.devicePixelRatio;

  ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const items = sortResultsAsc(results).filter((item) =>
    SETTLED_RESULTS.includes(normalizeText(item.result))
  );

  if (!items.length) return;

  let cumulative = 0;

  const points = items.map((item, index) => {
    cumulative += getResultProfit(item);

    return {
      xIndex: index,
      yValue: cumulative,
    };
  });

  const values = points.map((p) => p.yValue);
  const minY = Math.min(0, ...values);
  const maxY = Math.max(0, ...values);
  const pad = 28;

  const yRange = maxY - minY || 1;

  function xFor(index) {
    if (points.length === 1) return width / 2;
    return pad + (index / (points.length - 1)) * (width - pad * 2);
  }

  function yFor(value) {
    return height - pad - ((value - minY) / yRange) * (height - pad * 2);
  }

  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.25;

  for (let i = 0; i <= 4; i += 1) {
    const y = pad + (i / 4) * (height - pad * 2);
    ctx.beginPath();
    ctx.moveTo(pad, y);
    ctx.lineTo(width - pad, y);
    ctx.stroke();
  }

  ctx.globalAlpha = 1;
  ctx.lineWidth = 2;
  ctx.beginPath();

  points.forEach((point, index) => {
    const x = xFor(index);
    const y = yFor(point.yValue);

    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();

  const last = points[points.length - 1];
  ctx.beginPath();
  ctx.arc(xFor(last.xIndex), yFor(last.yValue), 4, 0, Math.PI * 2);
  ctx.fill();

  ctx.font = "12px system-ui, -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.globalAlpha = 0.8;
  ctx.fillText(fmtProfit(last.yValue), pad, pad - 8);
  ctx.globalAlpha = 1;
}

function setupDisclosureButtons() {
  qsa("[data-toggle-target]").forEach((button) => {
    const targetSelector = button.dataset.toggleTarget;
    const target = targetSelector ? qs(targetSelector) : null;

    if (!target) return;

    button.addEventListener("click", (event) => {
      event.preventDefault();

      const visible = isHistoryVisible(target);

      if (visible) {
        hideHistoryElement(target);
        button.setAttribute("aria-expanded", "false");

        if (button.dataset.closedText) {
          button.textContent = button.dataset.closedText;
        }

        return;
      }

      showHistoryElement(target);
      button.setAttribute("aria-expanded", "true");

      if (button.dataset.openText) {
        button.textContent = button.dataset.openText;
      }
    });
  });
}

function activateNavigation() {
  const page = document.body.dataset.page || "";

  qsa("[data-nav]").forEach((link) => {
    if (link.dataset.nav === page) {
      link.classList.add("active");
    }
  });
}

async function init() {
  activateNavigation();
  setupDisclosureButtons();

  const [predictions, results, stats] = await Promise.all([
    loadJsonFromCandidates(DATA_CANDIDATES.predictions, []),
    loadJsonFromCandidates(DATA_CANDIDATES.results, []),
    loadJsonFromCandidates(DATA_CANDIDATES.stats, {}),
  ]);

  const safePredictions = Array.isArray(predictions) ? predictions : [];
  const safeResults = Array.isArray(results) ? results : [];
  const safeStats = stats && typeof stats === "object" && !Array.isArray(stats) ? stats : {};

  fillStats(safeStats);
  fillDetailTables(safeStats);
  fillDailyTable(safeResults);
  renderRecentResults(safeResults);
  renderPredictions(safePredictions);
  fillPredictionStats(safePredictions);
  setupFullHistory(safeResults);
  drawProfitChart(safeResults);
}

document.addEventListener("DOMContentLoaded", init);
