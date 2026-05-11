const DATA_PATHS = {
  predictions: "public/data/totals_predictions.json",
  results: "public/data/totals_results.json",
  stats: "public/data/totals_stats.json",
};

const $ = (id) => document.getElementById(id);
const page = document.body.dataset.page || "home";

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

function num(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function fmt(value, decimals = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return n.toLocaleString("bs-BA", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function pct(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `${fmt(n, 2)}%` : "--";
}

function profit(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${n > 0 ? "+" : ""}${fmt(n, 2)}u`;
}

function dt(item) {
  return `${item.date || ""} ${item.time || ""}`.trim() || "Vrijeme nije dostupno";
}

function sideLabel(side, line) {
  return `${String(side || "").toUpperCase()} ${line ?? ""}`.trim();
}

function badgeSide(side) {
  return String(side || "").toLowerCase() === "under" ? "badge-under" : "badge-over";
}

function badgeResult(result) {
  const r = String(result || "").toLowerCase();
  if (r === "win") return "badge-win";
  if (r === "push" || r === "void") return "badge-push";
  return "badge-loss";
}

function edgeLabel(edge) {
  const n = Number(edge);
  if (!Number.isFinite(n)) return "--";
  return `${n >= 0 ? "+" : ""}${fmt(n * 100, 2)}%`;
}

function predictionCard(item) {
  return `
    <article class="pick-card" data-side="${String(item.side || "").toLowerCase()}" data-type="${String(item.event_type || item.tour_level || "").toLowerCase()}">
      <div class="card-top">
        <div>
          <h3>${item.match || "Nepoznat meč"}</h3>
          <small>${dt(item)} · ${item.tournament || "Tennis"}</small>
        </div>
        <span class="badge ${badgeSide(item.side)}">${sideLabel(item.side, item.line)}</span>
      </div>
      <div class="meta-grid">
        <div><small>Kvota</small><strong>${item.odds ?? "--"}</strong></div>
        <div><small>Bookmaker</small><strong>${item.best_bookmaker || "--"}</strong></div>
        <div><small>Confidence</small><strong>${item.confidence ? fmt(item.confidence, 0) : "--"}</strong></div>
        <div><small>Quality</small><strong>${item.quality_score ? fmt(item.quality_score, 1) : "--"}</strong></div>
        <div><small>Edge</small><strong>${edgeLabel(item.edge)}</strong></div>
        <div><small>Stake</small><strong>${item.stake_label || item.stake || "--"}</strong></div>
      </div>
      <p class="card-copy">${item.round || item.event_type || item.tour_level || "Totals market"} · Model output filtriran za public stranicu.</p>
    </article>`;
}

function resultCard(item) {
  return `
    <article class="result-card">
      <div class="card-top">
        <div>
          <h3>${item.match || "Nepoznat meč"}</h3>
          <small>${dt(item)} · ${item.tournament || "Tennis"}</small>
        </div>
        <span class="badge ${badgeResult(item.result)}">${String(item.result || "").toUpperCase()}</span>
      </div>
      <div class="meta-grid">
        <div><small>Pick</small><strong>${sideLabel(item.side, item.line)}</strong></div>
        <div><small>Kvota</small><strong>${item.odds ?? "--"}</strong></div>
        <div><small>Score</small><strong>${item.final_score || "--"}</strong></div>
        <div><small>Total games</small><strong>${item.total_games ?? "--"}</strong></div>
        <div><small>Profit</small><strong>${profit(item.profit)}</strong></div>
        <div><small>Settled</small><strong>${item.settled_at ? "da" : "--"}</strong></div>
      </div>
    </article>`;
}

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

function renderHome(predictions, results, stats) {
  const active = Array.isArray(predictions) ? predictions.length : 0;
  setText("heroActivePicks", active);
  setText("statSettled", stats?.settled_picks ?? "--");
  setText("statWinRate", pct(stats?.win_rate));
  setText("statProfit", profit(stats?.profit));

  const terminal = $("terminalText");
  if (terminal) {
    if (!active) {
      terminal.textContent = "totals_predictions.json loaded: 0 active public picks\nsistem čeka nove validne markete...";
    } else {
      terminal.textContent = predictions.slice(0, 5).map(x => `${x.time || "--:--"}  ${x.match || "Unknown"}  →  ${sideLabel(x.side, x.line)} @ ${x.odds ?? "--"}`).join("\n");
    }
  }

  const predBox = $("predictionsPreview");
  if (predBox) predBox.innerHTML = active ? predictions.slice(0, 6).map(predictionCard).join("") : `<div class="empty-state">Trenutno nema aktivnih public pickova.</div>`;

  const resBox = $("resultsPreview");
  if (resBox) resBox.innerHTML = Array.isArray(results) && results.length ? results.slice(0, 6).map(resultCard).join("") : `<div class="empty-state">Još nema settled public rezultata.</div>`;
}

function renderPredictionsPage(predictions) {
  const arr = Array.isArray(predictions) ? predictions : [];
  setText("predActive", arr.length);
  setText("predUnder", arr.filter(x => String(x.side).toLowerCase() === "under").length);
  setText("predOver", arr.filter(x => String(x.side).toLowerCase() === "over").length);
  setText("predNext", arr[0]?.time || "--");

  const list = $("predictionsList");
  const render = (filter = "all") => {
    if (!list) return;
    let filtered = arr;
    if (filter === "under" || filter === "over") {
      filtered = arr.filter(x => String(x.side || "").toLowerCase() === filter);
    } else if (filter !== "all") {
      filtered = arr.filter(x => String(x.event_type || x.tour_level || "").toLowerCase().includes(filter));
    }
    list.innerHTML = filtered.length ? filtered.map(predictionCard).join("") : `<div class="empty-state">Nema pickova za ovaj filter.</div>`;
  };

  render("all");

  document.querySelectorAll("#predictionFilters .filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#predictionFilters .filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      render(btn.dataset.filter);
    });
  });
}

function renderResultsPage(results, stats) {
  setText("resTotal", stats?.total_picks ?? "--");
  setText("resSettled", stats?.settled_picks ?? "--");
  setText("resWinRate", pct(stats?.win_rate));
  setText("resProfitRoi", `${profit(stats?.profit)} / ${pct(stats?.roi)}`);

  const list = $("resultsList");
  if (list) {
    list.innerHTML = Array.isArray(results) && results.length ? results.map(resultCard).join("") : `<div class="empty-state">Nova public statistika je aktivirana. Rezultati će se prikazati nakon settle-a objavljenih pickova.</div>`;
  }
}

function activateNav() {
  document.querySelectorAll("[data-nav]").forEach(a => {
    if (a.dataset.nav === page) a.classList.add("active");
  });
}

async function init() {
  activateNav();

  const needsData = ["home", "predictions", "results"].includes(page);
  if (!needsData) return;

  const [predictions, results, stats] = await Promise.all([
    loadJson(DATA_PATHS.predictions, []),
    loadJson(DATA_PATHS.results, []),
    loadJson(DATA_PATHS.stats, {}),
  ]);

  if (page === "home") renderHome(predictions, results, stats);
  if (page === "predictions") renderPredictionsPage(predictions);
  if (page === "results") renderResultsPage(results, stats);
}

document.addEventListener("DOMContentLoaded", init);
