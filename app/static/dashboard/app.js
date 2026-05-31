const STORE_ID = "STORE_BLR_002";
const REFRESH_MS = 3000;

const ZONE_LABELS = {
  ENTRY: "Entry",
  BILLING: "Cash Counter",
  PMU: "PMU",
  GOOD_VIBES: "Good Vibes",
  DERMDOC: "DermDoc",
  MINIMALIST: "Minimalist",
  AQUALOGICA: "Aqualogica",
  LAKME_SKIN: "Lakme Skin",
  EB_KOREAN: "EB Korean",
  FACE_SHOP: "Face Shop",
  MAYBELLINE: "Maybelline",
  FACES_CANADA: "Faces Canada",
  LAKME_MAKEUP: "Lakme",
  COLORBAR_SUGAR: "Colorbar",
  SWISS_BEAUTY: "Swiss Beauty",
  RENEE_NY_BAE: "Renee NY Bae",
  ALPS_GOODNESS: "Alps Goodness",
  STREAX: "Streax",
  FRAGRANCE: "Fragrance",
  MAKEUP_UNIT: "Makeup Unit",
  ACCESSORIES: "Accessories",
};

let conversionChart, funnelChart, dwellChart;
let prevValues = {};

function fmtPct(value) {
  return (value * 100).toFixed(1);
}

function fmtDwell(ms) {
  return (ms / 1000).toFixed(0) + "s";
}

function animateValue(el, key, newVal, formatter = (v) => v) {
  const str = formatter(newVal);
  if (prevValues[key] !== str) {
    el.textContent = str;
    el.closest(".kpi")?.classList.add("flash");
    setTimeout(() => el.closest(".kpi")?.classList.remove("flash"), 600);
    prevValues[key] = str;
  }
}

function heatColor(score) {
  const t = Math.min(100, Math.max(0, score)) / 100;
  const r = Math.round(80 + t * 95);
  const g = Math.round(40 + t * 30);
  const b = Math.round(140 + t * 80);
  const a = 0.25 + t * 0.55;
  return `rgba(${r},${g},${b},${a})`;
}

function initCharts() {
  const convCtx = document.getElementById("conversionChart").getContext("2d");
  conversionChart = new Chart(convCtx, {
    type: "doughnut",
    data: {
      labels: ["Converted", "Not converted"],
      datasets: [{
        data: [0, 100],
        backgroundColor: ["#9b59ff", "rgba(255,255,255,0.06)"],
        borderWidth: 0,
        cutout: "72%",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: false }, tooltip: { enabled: true } },
      animation: { animateRotate: true, duration: 800 },
    },
  });

  const funnelCtx = document.getElementById("funnelChart").getContext("2d");
  funnelChart = new Chart(funnelCtx, {
    type: "bar",
    data: {
      labels: [],
      datasets: [{
        label: "Customers",
        data: [],
        backgroundColor: (ctx) => {
          const g = ctx.chart.ctx.createLinearGradient(0, 0, 400, 0);
          g.addColorStop(0, "#9b59ff");
          g.addColorStop(1, "#e056fd");
          return g;
        },
        borderRadius: 8,
        barThickness: 28,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#9b8fb0" } },
        y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#9b8fb0" }, beginAtZero: true },
      },
      animation: { duration: 600 },
    },
  });

  const dwellCtx = document.getElementById("dwellChart").getContext("2d");
  dwellChart = new Chart(dwellCtx, {
    type: "bar",
    data: {
      labels: [],
      datasets: [{
        label: "Avg dwell (s)",
        data: [],
        backgroundColor: "rgba(155, 89, 255, 0.5)",
        borderColor: "#9b59ff",
        borderWidth: 1,
        borderRadius: 6,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#9b8fb0" } },
        y: { grid: { display: false }, ticks: { color: "#9b8fb0", font: { size: 11 } } },
      },
      animation: { duration: 600 },
    },
  });
}

async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

function renderMetrics(m) {
  const rate = fmtPct(m.conversion_rate);
  const rateEl = document.getElementById("conversionRate");
  rateEl.textContent = rate;
  rateEl.classList.add("bump");
  setTimeout(() => rateEl.classList.remove("bump"), 400);

  document.getElementById("conversionSub").textContent =
    `${m.converted_visitors} of ${m.unique_visitors} visitors converted · ${m.date}`;
  document.getElementById("convertedCount").textContent = m.converted_visitors;
  document.getElementById("dateChip").textContent = m.date;

  animateValue(document.getElementById("uniqueVisitors"), "visitors", m.unique_visitors);
  animateValue(document.getElementById("queueDepth"), "queue", m.current_queue_depth);
  animateValue(document.getElementById("abandonRate"), "abandon", m.queue_abandonment_rate, (v) => fmtPct(v) + "%");

  const convertedPct = m.unique_visitors ? m.conversion_rate * 100 : 0;
  conversionChart.data.datasets[0].data = [convertedPct, Math.max(0, 100 - convertedPct)];
  conversionChart.update("active");

  const dwellEntries = Object.entries(m.avg_dwell_by_zone || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);
  dwellChart.data.labels = dwellEntries.map(([z]) => ZONE_LABELS[z] || z.replace(/_/g, " "));
  dwellChart.data.datasets[0].data = dwellEntries.map(([, ms]) => ms / 1000);
  dwellChart.update("active");
}

function renderFunnel(f) {
  const track = document.getElementById("funnelTrack");
  track.innerHTML = f.stages
    .map(
      (s, i) => `
    <div class="funnel-step" style="animation-delay:${i * 0.08}s">
      <div class="funnel-step-name">${s.stage}</div>
      <div class="funnel-step-count">${s.count}</div>
      <div class="funnel-step-drop ${s.drop_off_pct === 0 ? "zero" : ""}">
        ${s.drop_off_pct === 0 ? "—" : "↓ " + s.drop_off_pct.toFixed(1) + "% drop"}
      </div>
    </div>`
    )
    .join("");

  funnelChart.data.labels = f.stages.map((s) => s.stage);
  funnelChart.data.datasets[0].data = f.stages.map((s) => s.count);
  funnelChart.update("active");
}

function renderHeatmap(h) {
  const badge = document.getElementById("confidenceBadge");
  badge.textContent = h.data_confidence + " confidence";
  badge.className = "badge" + (h.data_confidence === "LOW" ? " low" : "");

  const grid = document.getElementById("heatmapGrid");
  if (!h.zones.length) {
    grid.innerHTML = '<div class="empty-state">No zone data yet</div>';
    return;
  }

  grid.innerHTML = h.zones
    .map(
      (z) => `
    <div class="zone-tile" style="background:${heatColor(z.normalized_score)}" title="${z.zone_id}">
      <div class="zone-name">${ZONE_LABELS[z.zone_id] || z.zone_id.replace(/_/g, " ")}</div>
      <div class="zone-score">${Math.round(z.normalized_score)}</div>
      <div class="zone-visits">${z.visit_frequency} visits · ${fmtDwell(z.avg_dwell_ms)} avg</div>
    </div>`
    )
    .join("");
}

function renderAnomalies(a) {
  document.getElementById("anomalyCount").textContent = a.anomalies.length;
  const list = document.getElementById("anomalyList");

  if (!a.anomalies.length) {
    list.innerHTML = '<div class="empty-state">✓ No active anomalies — store operating normally</div>';
    return;
  }

  list.innerHTML = a.anomalies
    .map(
      (item, i) => `
    <div class="anomaly-item ${item.severity}" style="animation-delay:${i * 0.06}s">
      <div class="anomaly-top">
        <span class="anomaly-type">${item.anomaly_type.replace(/_/g, " ")}</span>
        <span class="anomaly-severity ${item.severity}">${item.severity}</span>
      </div>
      <p class="anomaly-msg">${item.message}</p>
      <p class="anomaly-action">→ ${item.suggested_action}</p>
    </div>`
    )
    .join("");
}

function renderHealth(h) {
  const pill = document.getElementById("livePill");
  const label = document.getElementById("liveLabel");
  const statusEl = document.getElementById("systemStatus");
  const lastEl = document.getElementById("lastEvent");

  const store = h.stores?.[0];
  const isLive = h.status === "ok" && store && !store.is_stale;

  pill.classList.toggle("degraded", !isLive);
  label.textContent = isLive ? "Live" : "Degraded";

  statusEl.textContent = h.status === "ok" ? "Healthy" : "Degraded";
  statusEl.style.color = h.status === "ok" ? "var(--green)" : "var(--orange)";

  if (store?.last_event_at) {
    const d = new Date(store.last_event_at);
    lastEl.textContent = "Last event · " + d.toLocaleString();
  } else {
    lastEl.textContent = "No events ingested yet";
  }
}

async function refresh() {
  try {
    const base = `/stores/${STORE_ID}`;
    const [metrics, funnel, heatmap, anomalies, health] = await Promise.all([
      fetchJSON(`${base}/metrics`),
      fetchJSON(`${base}/funnel`),
      fetchJSON(`${base}/heatmap`),
      fetchJSON(`${base}/anomalies`),
      fetchJSON("/health"),
    ]);

    renderMetrics(metrics);
    renderFunnel(funnel);
    renderHeatmap(heatmap);
    renderAnomalies(anomalies);
    renderHealth(health);

    document.getElementById("lastUpdated").textContent = new Date().toLocaleTimeString();
  } catch (err) {
    document.getElementById("liveLabel").textContent = "Offline";
    document.getElementById("livePill").classList.add("degraded");
    console.error(err);
  }
}

function startRefreshLoop() {
  let countdown = REFRESH_MS / 1000;
  setInterval(() => {
    countdown -= 1;
    if (countdown <= 0) {
      refresh();
      countdown = REFRESH_MS / 1000;
    }
    document.getElementById("refreshTimer").textContent = countdown;
  }, 1000);
}

document.addEventListener("DOMContentLoaded", () => {
  initCharts();
  refresh();
  startRefreshLoop();
});
