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

  return n.toLocaleString("bs-BA", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
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
    <article class="pick-card">
      <div class="pick-card-top">
        <div>
          <p class="eyebrow">${dt(item)} · ${item.tournament || "Tennis"}</p>
          <h3>${item.match || "Nepoznat meč"}</h3>
        </div>
        <span class="badge ${badgeSide(item.side)}">${sideLabel(item.side, item.line)}</span>
      </div>

      <div class="pick-grid">
        <div>
          <span>Koef</span>
          <strong>${item.odds ?? "--"}</strong>
        </div>
        <div>
          <span>Bookmaker</span>
          <strong>${item.best_bookmaker || "--"}</strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>${item.confidence ? fmt(item.confidence, 0) : "--"}</strong>
        </div>
        <div>
          <span>Quality</span>
          <strong>${item.quality_score ? fmt(item.quality_score, 1) : "--"}</strong>
        </div>
        <div>
          <span>Edge</span>
          <strong>${edgeLabel(item.edge)}</strong>
        </div>
        <div>
          <span>Stake</span>
          <strong>${item.stake_label || item.stake || "--"}</strong>
        </div>
      </div>

      <p class="muted">
        ${item.round || item.event_type || item.tour_level || "Totals market"} · Model output filtriran za public stranicu.
      </p>

      <a class="btn primary full" href="platforme.html">Preporučena platforma</a>
    </article>
  `;
}

function resultCard(item) {
  return `
    <article class="pick-card result-card">
      <div class="pick-card-top">
        <div>
          <p class="eyebrow">${dt(item)} · ${item.tournament || "Tennis"}</p>
          <h3>${item.match || "Nepoznat meč"}</h3>
        </div>
        <span class="badge ${badgeResult(item.result)}">${String(item.result || "").toUpperCase()}</span>
      </div>

      <div class="pick-grid">
        <div>
          <span>Pick</span>
          <strong>${sideLabel(item.side, item.line)}</strong>
        </div>
        <div>
          <span>Koef</span>
          <strong>${item.odds ?? "--"}</strong>
        </div>
        <div>
          <span>Score</span>
          <strong>${item.final_score || "--"}</strong>
        </div>
        <div>
          <span>Total games</span>
          <strong>${item.total_games ?? "--"}</strong>
        </div>
        <div>
          <span>Profit</span>
          <strong>${profit(item.public_profit ?? item.profit)}</strong>
        </div>
        <div>
          <span>Settled</span>
          <strong>${item.settled_at ? "da" : "--"}</strong>
        </div>
      </div>
    </article>
  `;
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
      terminal.textContent =
        "totals_predictions.json loaded: 0 active public picks\nsistem čeka nove validne markete...";
    } else {
      terminal.textContent = predictions
        .slice(0, 5)
        .map((x) => `${x.time || "--:--"} ${x.match || "Unknown"} → ${sideLabel(x.side, x.line)} @ ${x.odds ?? "--"}`)
        .join("\n");
    }
  }

  const predBox = $("predictionsPreview");

  if (predBox) {
    predBox.innerHTML = active
      ? predictions.slice(0, 6).map(predictionCard).join("")
      : `<p class="muted">Trenutno nema aktivnih public pickova.</p>`;
  }

  const resBox = $("resultsPreview");

  if (resBox) {
    resBox.innerHTML = Array.isArray(results) && results.length
      ? results.slice(0, 6).map(resultCard).join("")
      : `<p class="muted">Još nema settled public rezultata.</p>`;
  }
}

function renderPredictionsPage(predictions) {
  const arr = Array.isArray(predictions) ? predictions : [];

  setText("predActive", arr.length);
  setText("predUnder", arr.filter((x) => String(x.side).toLowerCase() === "under").length);
  setText("predOver", arr.filter((x) => String(x.side).toLowerCase() === "over").length);
  setText("predNext", arr[0]?.time || "--");

  const list = $("predictionsList");

  const render = (filter = "all") => {
    if (!list) return;

    let filtered = arr;

    if (filter === "under" || filter === "over") {
      filtered = arr.filter((x) => String(x.side || "").toLowerCase() === filter);
    } else if (filter !== "all") {
      filtered = arr.filter((x) =>
        String(x.event_type || x.tour_level || "").toLowerCase().includes(filter)
      );
    }

    list.innerHTML = filtered.length
      ? filtered.map(predictionCard).join("")
      : `<p class="muted">Nema pickova za ovaj filter.</p>`;
  };

  render("all");

  document.querySelectorAll("#predictionFilters .filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#predictionFilters .filter-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      render(btn.dataset.filter);
    });
  });
}

function renderFullHistory(results, filter = "all") {
  const table = document.querySelector("[data-full-history-table]");
  if (!table) return;

  const items = (Array.isArray(results) ? results : [])
    .filter((x) => {
      const result = String(x.result || "").toLowerCase();

      if (!["win", "loss", "void", "push"].includes(result)) return false;
      if (filter === "all") return true;

      return result === filter;
    })
    .sort((a, b) => {
      return `${b.date || ""} ${b.time || ""}`.localeCompare(`${a.date || ""} ${a.time || ""}`);
    });

  if (!items.length) {
    table.innerHTML = `<p class="muted">Nema rezultata za odabrani filter.</p>`;
    return;
  }

  const rows = items.map((r) => {
    const result = String(r.result || "").toLowerCase();

    return `
      <tr>
        <td>${r.date || "—"} ${r.time || ""}</td>
        <td>
          <strong>${r.match || "—"}</strong><br>
          <small>${r.tournament || "Tennis"}</small>
        </td>
        <td>${r.bet || sideLabel(r.side, r.line)}</td>
        <td>${fmt(r.odds, 2)}</td>
        <td>${fmt(r.public_stake ?? r.stake, 2)}u</td>
        <td>
          <span class="badge ${badgeResult(result)}">${result.toUpperCase()}</span>
        </td>
        <td>${r.final_score || "—"}</td>
        <td>${profit(r.public_profit ?? r.profit)}</td>
      </tr>
    `;
  }).join("");

  table.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Datum</th>
          <th>Meč</th>
          <th>Tip</th>
          <th>Koef</th>
          <th>Ulog</th>
          <th>Rezultat</th>
          <th>Score</th>
          <th>Profit</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function setupFullHistory(results) {
  const toggle = document.querySelector("[data-history-toggle]");
  const tools = document.querySelector("[data-history-tools]");
  const wrap = document.querySelector("[data-full-history]");
  const filterButtons = document.querySelectorAll("[data-history-filter]");

  if (!toggle || !wrap) return;

  let opened = false;
  let activeFilter = "all";

  toggle.addEventListener("click", () => {
    opened = !opened;

    wrap.hidden = !opened;

    if (tools) {
      tools.hidden = !opened;
    }

    toggle.textContent = opened ? "Sakrij rezultate" : "Prikaži sve rezultate";

    if (opened) {
      renderFullHistory(results, activeFilter);
    }
  });

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeFilter = button.dataset.historyFilter || "all";

      filterButtons.forEach((b) => b.classList.remove("active"));
      button.classList.add("active");

      renderFullHistory(results, activeFilter);
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
    list.innerHTML = Array.isArray(results) && results.length
      ? results.slice(0, 12).map(resultCard).join("")
      : `<p class="muted">Nova public statistika je aktivirana. Rezultati će se prikazati nakon settle-a objavljenih pickova.</p>`;
  }

  setupFullHistory(results);
}

function activateNav() {
  document.querySelectorAll("[data-nav]").forEach((a) => {
    if (a.dataset.nav === page) {
      a.classList.add("active");
    }
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

  if (page === "home") {
    renderHome(predictions, results, stats);
  }

  if (page === "predictions") {
    renderPredictionsPage(predictions);
  }

  if (page === "results") {
    renderResultsPage(results, stats);
  }
}

document.addEventListener("DOMContentLoaded", init);
