const sportIcons = {
  football: "⚽",
  basketball: "🏀",
  tennis: "🎾",
  hockey: "🏒",
  baseball: "⚾"
};

const AFFILIATE_URL = "https://stzns.lynmonkel.com/?mid=309891_1838278";

let profitChartInstance = null;

// ------------------------
// HELPERS
// ------------------------
function capitalize(text) {
  if (!text || typeof text !== "string") return "";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function safeNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

// ------------------------
// LOAD PREDICTIONS + LAST UPDATED
// ------------------------
async function loadPredictions() {
  try {
    const response = await fetch("./predictions.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Predictions fetch failed: ${response.status}`);
    }

    const predictions = await response.json();
    renderPredictions(Array.isArray(predictions) ? predictions : []);

    const now = new Date();
    const formatted =
      now.toLocaleDateString("en-GB") +
      " • " +
      now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const el = document.getElementById("last-updated");
    if (el) {
      el.textContent = `Updated • ${formatted}`;
    }
  } catch (error) {
    console.error("Error loading predictions!", error);

    const container = document.getElementById("predictions-container");
    if (container) {
      container.innerHTML = `
        <div class="prediction-card prediction-card--empty">
          <p>Predictions are temporarily unavailable. Please refresh again later.</p>
        </div>
      `;
    }
  }
}

// ------------------------
// CONFIDENCE SYSTEM
// ------------------------
function getConfidenceData(conf) {
  const confidence = safeNumber(conf);

  if (confidence < 60) {
    return {
      label: "🟡 Medium",
      units: "💸 1u",
      color: "#ffc107"
    };
  }

  if (confidence < 75) {
    return {
      label: "🟢 Strong",
      units: "💸 1.5u",
      color: "#28a745"
    };
  }

  return {
    label: "🔥 Very Strong",
    units: "💸 2u",
    color: "#d4af37"
  };
}

// ------------------------
// TIME UNTIL MATCH
// ------------------------
function getKickoffStatus(dateStr, timeStr) {
  if (!dateStr || !timeStr) return "";

  const [year, month, day] = dateStr.split("-").map(Number);
  const [hours, minutes] = timeStr.split(":").map(Number);

  if (
    !Number.isFinite(year) ||
    !Number.isFinite(month) ||
    !Number.isFinite(day) ||
    !Number.isFinite(hours) ||
    !Number.isFinite(minutes)
  ) {
    return "";
  }

  const now = new Date();
  const matchTime = new Date(year, month - 1, day, hours, minutes, 0, 0);
  const diffMinutes = Math.floor((matchTime - now) / 60000);

  if (diffMinutes <= 0) return "";
  if (diffMinutes < 60) return `⏰ Starts in ${diffMinutes} min`;
  if (diffMinutes < 180) return `🕒 Starts in ${Math.floor(diffMinutes / 60)}h`;

  return "";
}

// ------------------------
// RENDER CARDS
// ------------------------
function renderPredictions(data) {
  const container = document.getElementById("predictions-container");
  if (!container) return;

  container.innerHTML = "";

  if (!data.length) {
    container.innerHTML = `
      <div class="prediction-card prediction-card--empty">
        <p>No predictions available right now.</p>
      </div>
    `;
    return;
  }

  data.forEach((p, index) => {
    const confidenceValue = safeNumber(p.confidence);
    const conf = getConfidenceData(confidenceValue);
    const kickoff = getKickoffStatus(p.date, p.time);
    const sport = capitalize(p.sport || "sport");
    const icon = sportIcons[p.sport] || "🎯";
    const odds = safeNumber(p.odds, null);

    const card = document.createElement("article");
    card.className = "prediction-card";

    card.innerHTML = `
      <div class="prediction-card__meta prediction-meta">
        <span>📅 ${p.date || "-"}</span>
        <span>🕒 ${p.time || "-"}</span>
        <span>${icon} ${sport}</span>
        <span>🏆 ${p.league || "-"}</span>
      </div>

      <h3 class="prediction-card__match">${p.match || "Unknown match"}</h3>

      <p class="prediction-card__bet bet-type">
        <strong>Tip:</strong> ${p.bet || "-"}
      </p>

      ${odds ? `<p class="prediction-card__odds"><strong>Odds:</strong> ${odds.toFixed(2)}</p>` : ""}

      ${kickoff ? `<p class="prediction-card__kickoff kickoff">${kickoff}</p>` : ""}

      <div class="prediction-card__analysis ai-reasoning">
        <p><strong>AI Analysis:</strong> ${p.reasoning || "No analysis available."}</p>
      </div>

      <div class="prediction-card__chart-wrap">
        <canvas id="chart${index}" aria-label="Confidence chart for ${p.match || "prediction"}"></canvas>
      </div>

      <p class="prediction-card__confidence confidence-label" style="color:${conf.color}">
        ${conf.label} • ${conf.units}
      </p>

      <a href="${AFFILIATE_URL}" target="_blank" rel="noopener noreferrer" class="btn btn--primary">
        Check Best Odds 💥
      </a>
    `;

    container.appendChild(card);

    const chartCanvas = document.getElementById(`chart${index}`);
    if (chartCanvas) {
      new Chart(chartCanvas, {
        type: "doughnut",
        data: {
          datasets: [{
            data: [confidenceValue, Math.max(0, 100 - confidenceValue)],
            backgroundColor: [conf.color, "#2a2f3a"],
            borderWidth: 0
          }]
        },
        options: {
          cutout: "78%",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false }
          }
        }
      });
    }
  });
}

// ------------------------
// STATS + REAL PROFIT CHART
// ------------------------
async function loadStats() {
  try {
    const res = await fetch("./results.json", { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`Results fetch failed: ${res.status}`);
    }

    const data = await res.json();
    if (!Array.isArray(data)) return;

    let total = 0;
    let wins = 0;
    let profit = 0;
    let totalStaked = 0;
    let avgOddsSum = 0;
    let avgOddsCount = 0;

    const dailyProfit = {};

    data.forEach((p) => {
      if (p.result === "pending") return;

      let units = 1;
      if (safeNumber(p.confidence) >= 75) units = 2;
      else if (safeNumber(p.confidence) >= 60) units = 1.5;

      total++;

      if (typeof p.odds === "number") {
        avgOddsSum += p.odds;
        avgOddsCount++;
      }

      let pickProfit = 0;

      if (p.result === "win") {
        wins++;
        totalStaked += units;

        if (typeof p.odds === "number") {
          pickProfit = (p.odds - 1) * units;
        } else {
          pickProfit = units;
        }
      } else if (p.result === "loss") {
        totalStaked += units;
        pickProfit = -units;
      } else if (p.result === "storno") {
        pickProfit = 0;
      }

      profit += pickProfit;

      const dateKey = p.date || "Unknown";
      if (!dailyProfit[dateKey]) dailyProfit[dateKey] = 0;
      dailyProfit[dateKey] += pickProfit;
    });

    const roi = totalStaked > 0 ? ((profit / totalStaked) * 100).toFixed(1) : "0.0";
    const avgOdds = avgOddsCount > 0 ? (avgOddsSum / avgOddsCount).toFixed(2) : "0.00";

    const statBoxes = document.querySelectorAll(".stat-box h3");
    if (statBoxes.length >= 4 && total > 0) {
      statBoxes[0].textContent = total;
      statBoxes[1].textContent = wins;
      statBoxes[2].textContent = avgOdds;
      statBoxes[3].textContent = `${roi}%`;
    }

    const profitCanvas = document.getElementById("profitChart");
    if (!profitCanvas) return;

    const sortedDates = Object.keys(dailyProfit).sort();
    let runningProfit = 0;

    const labels = [];
    const values = [];

    sortedDates.forEach((date) => {
      runningProfit += dailyProfit[date];
      labels.push(date);
      values.push(Number(runningProfit.toFixed(2)));
    });

    if (profitChartInstance) {
      profitChartInstance.destroy();
    }

    profitChartInstance = new Chart(profitCanvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Profit Growth (Units)",
          data: values,
          borderColor: "#d4af37",
          backgroundColor: "rgba(212, 175, 55, 0.12)",
          borderWidth: 3,
          tension: 0.3,
          fill: true,
          pointRadius: 0,
          pointHoverRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            ticks: { color: "#c7cfdb" },
            grid: { color: "rgba(255,255,255,0.08)" }
          },
          y: {
            ticks: { color: "#c7cfdb" },
            grid: { color: "rgba(255,255,255,0.08)" }
          }
        }
      }
    });
  } catch (e) {
    console.log("Stats error", e);
  }
}

// ------------------------
// TOGGLE HOW WE PLAY
// ------------------------
function initHowWePlayToggle() {
  const title = document.getElementById("howWePlayTitle");
  const content = document.getElementById("howWePlayContent");

  if (!title || !content) return;

  title.addEventListener("click", () => {
    const isHidden = content.classList.contains("hidden");
    content.classList.toggle("hidden");
    title.setAttribute("aria-expanded", String(isHidden));
  });
}

// ------------------------
// RUN
// ------------------------
document.addEventListener("DOMContentLoaded", () => {
  initHowWePlayToggle();
  loadPredictions();
  loadStats();
});
