const DATA_PATHS = {
  predictions: "public/data/totals_predictions.json",
  results: "public/data/totals_results.json",
  stats: "public/data/totals_stats.json",
};

const $ = (id) => document.getElementById(id);

async function loadJson(path, fallback) {
  try {
    const res = await fetch(path, {
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    return await res.json();
  } catch (error) {
    console.warn(`Could not load ${path}`, error);
    return fallback;
  }
}

function toNumber(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function formatNumber(value, decimals = 0) {
  const num = Number(value);

  if (!Number.isFinite(num)) {
    return "--";
  }

  return num.toLocaleString("bs-BA", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatPercent(value) {
  const num = Number(value);

  if (!Number.isFinite(num)) {
    return "--";
  }

  return `${formatNumber(num, 2)}%`;
}

function formatProfit(value) {
  const num = Number(value);

  if (!Number.isFinite(num)) {
    return "--";
  }

  const sign = num > 0 ? "+" : "";
  return `${sign}${formatNumber(num, 2)}u`;
}

function formatDateTime(item) {
  const date = item.date || "";
  const time = item.time || "";

  if (!date && !time) {
    return "Vrijeme nije dostupno";
  }

  return `${date} ${time}`.trim();
}

function sideLabel(side, line) {
  const normalized = String(side || "").toUpperCase();
  return `${normalized} ${line ?? ""}`.trim();
}

function badgeClassForSide(side) {
  return String(side || "").toLowerCase() === "under"
    ? "badge-under"
    : "badge-over";
}

function badgeClassForResult(result) {
  const normalized = String(result || "").toLowerCase();

  if (normalized === "win") {
    return "badge-win";
  }

  if (normalized === "push" || normalized === "void") {
    return "badge-push";
  }

  return "badge-loss";
}

function renderPredictionCard(item) {
  return `
    <article class="pick-card">
      <div class="card-top">
        <div>
          <h3>${item.match || "Nepoznat meč"}</h3>
          <small>${formatDateTime(item)}</small>
        </div>
        <span class="badge ${badgeClassForSide(item.side)}">
          ${sideLabel(item.side, item.line)}
        </span>
      </div>

      <div class="card-meta">
        <div>
          <small>Kvota</small>
          <strong>${item.odds ?? "--"}</strong>
        </div>

        <div>
          <small>Bookmaker</small>
          <strong>${item.best_bookmaker || "--"}</strong>
        </div>

        <div>
          <small>Confidence</small>
          <strong>${item.confidence ? formatNumber(item.confidence, 0) : "--"}</strong>
        </div>
      </div>

      <p class="card-copy">
        ${item.tournament || "Tennis"} · ${item.round || item.event_type || "Totals market"}
      </p>
    </article>
  `;
}

function renderResultCard(item) {
  return `
    <article class="pick-card">
      <div class="card-top">
        <div>
          <h3>${item.match || "Nepoznat meč"}</h3>
          <small>${formatDateTime(item)}</small>
        </div>
        <span class="badge ${badgeClassForResult(item.result)}">
          ${String(item.result || "").toUpperCase()}
        </span>
      </div>

      <div class="card-meta">
        <div>
          <small>Pick</small>
          <strong>${sideLabel(item.side, item.line)}</strong>
        </div>

        <div>
          <small>Score</small>
          <strong>${item.final_score || "--"}</strong>
        </div>

        <div>
          <small>Profit</small>
          <strong>${formatProfit(item.profit)}</strong>
        </div>
      </div>
    </article>
  `;
}

function renderPredictions(predictions) {
  const container = $("predictionsPreview");

  if (!container) {
    return;
  }

  if (!Array.isArray(predictions) || predictions.length === 0) {
    container.innerHTML = `<div class="empty-state">Trenutno nema aktivnih public pickova.</div>`;
    return;
  }

  container.innerHTML = predictions
    .slice(0, 6)
    .map(renderPredictionCard)
    .join("");
}

function renderResults(results) {
  const container = $("resultsPreview");

  if (!container) {
    return;
  }

  if (!Array.isArray(results) || results.length === 0) {
    container.innerHTML = `<div class="empty-state">Još nema public rezultata.</div>`;
    return;
  }

  container.innerHTML = results
    .slice(0, 6)
    .map(renderResultCard)
    .join("");
}

function renderStats(stats) {
  const statTotal = $("statTotal");
  const statWinRate = $("statWinRate");
  const statProfit = $("statProfit");
  const statRoi = $("statRoi");

  if (statTotal) {
    statTotal.textContent = stats?.total_picks ?? "--";
  }

  if (statWinRate) {
    statWinRate.textContent = formatPercent(stats?.win_rate);
  }

  if (statProfit) {
    statProfit.textContent = formatProfit(stats?.profit);
  }

  if (statRoi) {
    statRoi.textContent = formatPercent(stats?.roi);
  }
}

function renderHero(predictions, stats) {
  const heroTotalPicks = $("heroTotalPicks");
  const heroUpdated = $("heroUpdated");
  const terminalText = $("terminalText");

  const predictionCount = Array.isArray(predictions) ? predictions.length : 0;

  if (heroTotalPicks) {
    heroTotalPicks.textContent = predictionCount;
  }

  if (heroUpdated) {
    const now = new Date();
    heroUpdated.textContent = now.toLocaleTimeString("bs-BA", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  if (terminalText) {
    if (!predictionCount) {
      terminalText.textContent = "totals_predictions.json loaded: 0 active public picks";
      return;
    }

    const preview = predictions
      .slice(0, 4)
      .map((item) => {
        return `${item.time || "--:--"} ${item.match || "Unknown"} → ${sideLabel(item.side, item.line)} @ ${item.odds ?? "--"}`;
      })
      .join("\n");

    terminalText.textContent = preview;
  }
}

async function initTotalsPage() {
  const [predictions, results, stats] = await Promise.all([
    loadJson(DATA_PATHS.predictions, []),
    loadJson(DATA_PATHS.results, []),
    loadJson(DATA_PATHS.stats, {}),
  ]);

  renderPredictions(predictions);
  renderResults(results);
  renderStats(stats);
  renderHero(predictions, stats);

  console.log("Loaded totals predictions:", predictions);
  console.log("Loaded totals results:", results);
  console.log("Loaded totals stats:", stats);
}

document.addEventListener("DOMContentLoaded", initTotalsPage);
