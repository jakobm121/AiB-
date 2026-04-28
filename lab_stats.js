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
  home: "Home",
  draw: "Draw",
  away: "Away",
  over_2_5: "Over 2.5",
  under_2_5: "Under 2.5",
  btts_yes: "BTTS Yes",
  btts_no: "BTTS No",
  over_3_5: "Over 3.5",
  under_3_5: "Under 3.5"
};

function formatSigned(value, digits = 2) {
  const num = Number(value || 0);
  if (num > 0) return `+${num.toFixed(digits)}`;
  return num.toFixed(digits);
}

function getValueClass(value, positiveClass, negativeClass) {
  const num = Number(value || 0);
  if (num > 0) return positiveClass;
  if (num < 0) return negativeClass;
  return "lab-neutral";
}

function showLabError(message) {
  const totalPicks = document.getElementById("lab-total-picks");
  const hitRate = document.getElementById("lab-hit-rate");
  const profit = document.getElementById("lab-profit");
  const roi = document.getElementById("lab-roi");
  const tbody = document.getElementById("lab-stats-body");

  if (totalPicks) totalPicks.textContent = "ERR";
  if (hitRate) hitRate.textContent = "ERR";
  if (profit) profit.textContent = "ERR";
  if (roi) roi.textContent = "ERR";

  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="color:#ff6b6b;font-weight:700;">
          ${message}
        </td>
      </tr>
    `;
  }
}

async function loadLabStats() {
  try {
    const response = await fetch(`./lab_stats.json?v=${Date.now()}`, {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status} while loading lab_stats.json`);
    }

    const stats = await response.json();

    if (!stats || typeof stats !== "object") {
      throw new Error("Invalid lab_stats.json");
    }

    if (!stats.overall || !stats.by_bucket) {
      throw new Error("Missing overall or by_bucket");
    }

    renderLabSummary(stats.overall);
    renderLabBucketTable(stats.by_bucket);
  } catch (error) {
    console.error("Error loading lab stats:", error);
    showLabError(`Lab stats failed: ${error.message}`);
  }
}

function renderLabSummary(overall) {
  const totalPicks = document.getElementById("lab-total-picks");
  const hitRate = document.getElementById("lab-hit-rate");
  const profit = document.getElementById("lab-profit");
  const roi = document.getElementById("lab-roi");

  if (totalPicks) totalPicks.textContent = overall.picks ?? "-";
  if (hitRate) hitRate.textContent = overall.hit_rate != null ? `${overall.hit_rate}%` : "-";

  if (profit) {
    profit.textContent = overall.profit != null ? formatSigned(overall.profit) : "-";
    profit.className = getValueClass(overall.profit, "lab-profit-positive", "lab-profit-negative");
  }

  if (roi) {
    roi.textContent = overall.roi != null ? `${formatSigned(overall.roi)}%` : "-";
    roi.className = getValueClass(overall.roi, "lab-roi-positive", "lab-roi-negative");
  }
}

function renderLabBucketTable(byBucket) {
  const tbody = document.getElementById("lab-stats-body");
  if (!tbody) return;

  tbody.innerHTML = "";

  LAB_BUCKET_ORDER.forEach((bucketKey) => {
    const stats = byBucket[bucketKey];
    if (!stats) return;

    const tr = document.createElement("tr");
    const roiClass = getValueClass(stats.roi, "lab-roi-positive", "lab-roi-negative");
    const profitClass = getValueClass(stats.profit, "lab-profit-positive", "lab-profit-negative");

    tr.innerHTML = `
      <td>${LAB_BUCKET_LABELS[bucketKey] || bucketKey}</td>
      <td>${stats.picks ?? 0}</td>
      <td>${stats.wins ?? 0}</td>
      <td>${stats.losses ?? 0}</td>
      <td>${stats.avg_odds ?? 0}</td>
      <td>${stats.hit_rate != null ? stats.hit_rate + "%" : "-"}</td>
      <td class="${profitClass}">${formatSigned(stats.profit ?? 0)}</td>
      <td class="${roiClass}">${formatSigned(stats.roi ?? 0)}%</td>
    `;

    tbody.appendChild(tr);
  });
}

document.addEventListener("DOMContentLoaded", loadLabStats);
