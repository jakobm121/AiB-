const DATA_PATHS = {
  predictions: "public/data/totals_predictions.json",
  results: "public/data/totals_results.json",
  stats: "public/data/totals_stats.json"
};

const $ = (id) => document.getElementById(id);

async function loadJson(path, fallback) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(`Could not load ${path}`, error);
    return fallback;
  }
}

function formatNumber(value, decimals = 0) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "--";
  return num.toLocaleString("bs-BA", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

function formatPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "--";
  return `${formatNumber(num, 2)}%`;
}

function formatProfit(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "--";

  const sign = num > 0 ? "+" : "";
  return `${sign}${formatNumber(num, 2)}u`;
}

function formatDateTime(item) {
  const date = item.date || "";
  const time = item.time || "";
  if (!date && !time) return "Vrijeme nije dostupno";
  return `${date} ${time}`.trim();
}

function sideLabel(side, line) {
  const normalized = String(side || "").toUpperCase();
  return `${normalized} ${line ?? ""}`.trim();
}

function badgeClassForSide(side) {
  return String(side).toLowerCase() === "under" ? "badge-under" : "badge-over";
}

function badgeClassForResult(result) {
  return String(result).toLowerCase() === "win" ? "badge-win" : "badge-loss";
}

function renderPredictionCard(item) {
  return `
    <article class="pick-card">
      <div class="card-top">
        <div>
          <h3>${item.match || "Nepoznat meč"}</h3>
          <small>${formatDateTime(item)}</small>
        </div>
        <span class="badge ${badgeClassForSide(item.side)}">${sideLabel(item.side, item.line)}</span>
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
          <strong>${item.confidence ?
