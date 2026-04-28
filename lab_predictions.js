const LAB_BUCKET_ORDER = [
  "home",
  "draw",
  "away",
  "over_2_5",
  "under_2_5",
  "btts_yes",
  "btts_no",
  "over_3_5",
  "under_3_5"
];

const LAB_BUCKET_LABELS = {
  home: "Home Picks",
  draw: "Draw Picks",
  away: "Away Picks",
  over_2_5: "Over 2.5 Picks",
  under_2_5: "Under 2.5 Picks",
  btts_yes: "BTTS Yes Picks",
  btts_no: "BTTS No Picks",
  over_3_5: "Over 3.5 Picks",
  under_3_5: "Under 3.5 Picks"
};

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatPercent(value, digits = 1) {
  const num = Number(value);
  if (Number.isNaN(num)) return "-";
  return `${(num * 100).toFixed(digits)}%`;
}

function formatEdge(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return "-";
  const pct = (num * 100).toFixed(2);
  return `${num > 0 ? "+" : ""}${pct}%`;
}

function formatUpdatedDate(isoString) {
  if (!isoString) return "Updated • --";

  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return "Updated • --";

    const formatted =
      d.toLocaleDateString("en-GB") +
      " • " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    return `Updated • ${formatted}`;
  } catch {
    return "Updated • --";
  }
}

function getBucketBadge(bucket) {
  const map = {
    home: "🏠 Home",
    draw: "🤝 Draw",
    away: "✈️ Away",
    over_2_5: "📈 Over 2.5",
    under_2_5: "📉 Under 2.5",
    btts_yes: "⚽ BTTS Yes",
    btts_no: "🛡️ BTTS No",
    over_3_5: "🔥 Over 3.5",
    under_3_5: "❄️ Under 3.5"
  };
  return map[bucket] || bucket;
}

function createPickCard(pick, bucketKey) {
  const badge = getBucketBadge(bucketKey);

  return `
    <article class="prediction-card prediction-card--lab">
      <div class="prediction-meta">
        <span>📅 ${escapeHtml(pick.date || "-")}</span>
        <span>🕒 ${escapeHtml(pick.time || "-")}</span>
        <span>🏆 ${escapeHtml(pick.league || "-")}</span>
        <span>${escapeHtml(badge)}</span>
      </div>

      <h3>${escapeHtml(pick.match || "-")}</h3>

      <p class="bet-type">Tip: ${escapeHtml(pick.bet || "-")}</p>
      <p class="bet-odds">Odds: ${escapeHtml(pick.odds ?? "-")}</p>

      <div class="ai-reasoning">
        <p><strong>AI Analysis:</strong> ${escapeHtml(pick.reasoning || "No reasoning available.")}</p>
      </div>

      <div class="lab-pick-stats">
        <div class="lab-pick-stat">
          <span class="lab-pick-stat__label">Model Prob</span>
          <strong>${formatPercent(pick.model_prob)}</strong>
        </div>

        <div class="lab-pick-stat">
          <span class="lab-pick-stat__label">Implied Prob</span>
          <strong>${formatPercent(pick.implied_prob)}</strong>
        </div>

        <div class="lab-pick-stat">
          <span class="lab-pick-stat__label">Edge</span>
          <strong>${formatEdge(pick.edge)}</strong>
        </div>

        <div class="lab-pick-stat">
          <span class="lab-pick-stat__label">Books Used</span>
          <strong>${escapeHtml(pick.bookmakers_used ?? "-")}</strong>
        </div>
      </div>

      <p class="lab-flat-stake">Flat Stake • 1 Unit</p>

      <a href="https://stzns.lynmonkel.com/?mid=309891_1838278" class="btn">
        Check Best Odds 💥
      </a>
    </article>
  `;
}

function createBucketSection(bucketKey, picks) {
  const section = document.createElement("section");
  section.className = "lab-bucket";

  const title = LAB_BUCKET_LABELS[bucketKey] || bucketKey;
  const cardsHtml = picks.map((pick) => createPickCard(pick, bucketKey)).join("");

  section.innerHTML = `
    <div class="lab-bucket__header">
      <h2 class="lab-bucket__title">${escapeHtml(title)}</h2>
      <span class="lab-bucket__count">${picks.length}</span>
    </div>

    <div class="predictions-grid">
      ${cardsHtml}
    </div>
  `;

  return section;
}

function renderEmptyState(container) {
  container.innerHTML = `
    <div class="prediction-card prediction-card--lab">
      <h3>No lab picks in current window</h3>
      <p class="bet-type">The model did not find enough valid candidates for the current refresh window.</p>
      <div class="ai-reasoning">
        <p><strong>AI Analysis:</strong> This usually means the time window was narrow or the edge filters were too strict for the available matches.</p>
      </div>
    </div>
  `;
}

async function loadLabPredictions() {
  try {
    const response = await fetch("./lab_predictions.json", { cache: "no-store" });
    const payload = await response.json();

    const container = document.getElementById("predictions-container");
    const updatedEl = document.getElementById("last-updated");

    if (!container) return;

    if (updatedEl) {
      updatedEl.textContent = formatUpdatedDate(payload.generated_at);
    }

    container.innerHTML = "";

    const buckets = payload?.buckets || {};
    let totalPicks = 0;

    LAB_BUCKET_ORDER.forEach((bucketKey) => {
      const picks = Array.isArray(buckets[bucketKey]) ? buckets[bucketKey] : [];
      if (!picks.length) return;

      totalPicks += picks.length;
      container.appendChild(createBucketSection(bucketKey, picks));
    });

    if (totalPicks === 0) {
      renderEmptyState(container);
    }
  } catch (error) {
    console.error("Error loading lab predictions:", error);

    const container = document.getElementById("predictions-container");
    const updatedEl = document.getElementById("last-updated");

    if (updatedEl) {
      updatedEl.textContent = "Updated • error";
    }

    if (container) {
      container.innerHTML = `
        <div class="prediction-card prediction-card--lab">
          <h3>Lab predictions failed to load</h3>
          <p class="bet-type">Check lab_predictions.json and browser console.</p>
        </div>
      `;
    }
  }
}

document.addEventListener("DOMContentLoaded", loadLabPredictions);
