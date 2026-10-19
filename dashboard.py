"""Flask dashboard: daily temperatures compared with the climate normal."""

import logging
import os
import time

from flask import Flask, jsonify, render_template_string, request
from werkzeug.exceptions import HTTPException

import climate
from db import CITY_LAT, CITY_LON, CITY_NAME, TABLE, query

app = Flask(__name__)
log = logging.getLogger(__name__)

CACHE_SECONDS = 600  # data changes once a day, so recompute at most every 10 minutes
_cache = {"time": 0.0, "data": None}


def get_analysis():
    """Load all rows and run the climate analysis, cached for a few minutes."""
    if _cache["data"] is None or time.time() - _cache["time"] > CACHE_SECONDS:
        rows = query(f"SELECT date, temp_max, temp_min FROM {TABLE} WHERE temp_max IS NOT NULL "
                     f"AND temp_min IS NOT NULL ORDER BY date")
        _cache["data"] = climate.analyse(rows)
        _cache["time"] = time.time()
    return _cache["data"]


@app.errorhandler(Exception)
def handle_error(err):
    if isinstance(err, HTTPException):  # normal 404s etc. pass through unchanged
        return err
    log.exception("Request failed")
    return jsonify(error="Could not load weather data. Is the database reachable?"), 503


def empty():
    return jsonify(error="No data yet. Run fetch_weather.py first."), 404


@app.route("/api/summary")
def api_summary():
    data = get_analysis()
    if not data:
        return empty()
    return jsonify(city=CITY_NAME, lat=CITY_LAT, lon=CITY_LON, **data["summary"])


@app.route("/api/daily")
def api_daily():
    data = get_analysis()
    if not data:
        return empty()
    days = max(30, min(request.args.get("days", 365, type=int), 20000))
    return jsonify(data["daily"][-days:])


@app.route("/api/yearly")
def api_yearly():
    data = get_analysis()
    if not data:
        return empty()
    return jsonify(data["years"])


@app.route("/api/data")
def api_data():
    """All stored days (kept for compatibility with the first version of the API)."""
    data = get_analysis()
    return jsonify([{k: d[k] for k in ("date", "temp_max", "temp_min")} for d in data["daily"]] if data else [])


@app.route("/health")
def health():
    """For uptime checks: is the database reachable and how fresh is the data?"""
    last = query(f"SELECT MAX(date) FROM {TABLE}")[0][0]
    return jsonify(ok=True, last_date=last.isoformat() if last else None)


HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ city }} Weather · Climate Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root { --bg:#0a0f1e; --card:#111827; --line:#1e293b; --text:#e2e8f0; --muted:#94a3b8; --dim:#64748b;
          --hot:#f87171; --cold:#60a5fa; --accent:#a78bfa; }
  body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text);
         min-height: 100vh; padding: 2rem 1rem; }
  .wrap { max-width: 1200px; margin: 0 auto; }
  h1 { font-size: 2rem; font-weight: 700; margin-bottom: .3rem;
       background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text;
       -webkit-text-fill-color: transparent; display: inline-block; }
  .badge { display: inline-flex; align-items: center; gap: .4rem; margin-left: .75rem; vertical-align: middle;
           background: #052e16; color: #4ade80; border: 1px solid #166534; border-radius: 9999px;
           padding: .2rem .7rem; font-size: .75rem; font-weight: 600; }
  .subtitle { color: var(--muted); margin-bottom: 1.75rem; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
  .stat { background: var(--card); border: 1px solid var(--line); border-radius: .75rem; padding: 1.1rem; }
  .stat-label { font-size: .72rem; color: var(--dim); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .4rem; }
  .stat-value { font-size: 1.6rem; font-weight: 700; }
  .stat-sub { font-size: .8rem; color: var(--muted); margin-top: .3rem; }
  .warm { color: var(--hot); } .cool { color: var(--cold); } .neutral { color: var(--accent); }
  .tabs { display: flex; flex-wrap: wrap; gap: .6rem; margin-bottom: 1rem; }
  .tab { padding: .5rem 1.2rem; border-radius: 9999px; border: 1px solid #334155; background: transparent;
         color: var(--muted); cursor: pointer; font: inherit; font-size: .9rem; }
  .tab.active { background: linear-gradient(135deg, #3b82f6, #8b5cf6); border-color: transparent; color: #fff; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 1rem; padding: 1.5rem; margin-bottom: 1rem; }
  .section { display: none; } .section.visible { display: block; }
  .section p { color: var(--muted); font-size: .9rem; margin-bottom: 1rem; }
  .chart-box { position: relative; height: 380px; }
  .error { display: none; background: #450a0a; border: 1px solid #7f1d1d; color: #fecaca;
           border-radius: .75rem; padding: 1rem; margin-bottom: 1rem; }
  .footer { text-align: center; color: var(--dim); font-size: .78rem; margin-top: 1.5rem; }
</style>
</head>
<body>
<div class="wrap">
  <h1>🌡️ {{ city }} Weather</h1><span class="badge" id="badge">Updated daily</span>
  <p class="subtitle" id="subtitle">Daily temperatures compared with the climate normal</p>

  <div class="error" id="error"></div>

  <div class="stats">
    <div class="stat"><div class="stat-label" id="latestLabel">Latest day</div>
      <div class="stat-value" id="latest">—</div><div class="stat-sub" id="latestSub"></div></div>
    <div class="stat"><div class="stat-label" id="yearLabel">This year so far</div>
      <div class="stat-value" id="year">—</div><div class="stat-sub" id="yearSub"></div></div>
    <div class="stat"><div class="stat-label">Warming trend</div>
      <div class="stat-value" id="trend">—</div><div class="stat-sub" id="trendSub"></div></div>
    <div class="stat"><div class="stat-label">Record high</div>
      <div class="stat-value warm" id="high">—</div><div class="stat-sub" id="highSub"></div></div>
    <div class="stat"><div class="stat-label">Record low</div>
      <div class="stat-value cool" id="low">—</div><div class="stat-sub" id="lowSub"></div></div>
  </div>

  <div class="tabs">
    <button class="tab active" data-tab="recent">Last 12 months</button>
    <button class="tab" data-tab="years">Year by year</button>
    <button class="tab" data-tab="hot">Hot days</button>
  </div>

  <div class="card">
    <div class="section visible" id="tab-recent">
      <p>Daily highs and lows. The shaded band is the normal range for each day of the year.</p>
      <div class="chart-box"><canvas id="recentChart"></canvas></div>
    </div>
    <div class="section" id="tab-years">
      <p>How much warmer (red) or colder (blue) than normal each year was, on average.</p>
      <div class="chart-box"><canvas id="yearsChart"></canvas></div>
    </div>
    <div class="section" id="tab-hot">
      <p>Days per year with a high of 30 °C or more.</p>
      <div class="chart-box"><canvas id="hotChart"></canvas></div>
    </div>
  </div>

  <div class="footer" id="footer">Data: Open-Meteo historical weather API · {{ city }} ({{ lat }}°, {{ lon }}°)</div>
</div>

<script>
const GRID = '#1e293b', TICK = '#64748b';
const fmt = v => (v > 0 ? '+' : '') + v.toFixed(1) + '°C';
const warmth = v => v > 0.05 ? 'warm' : (v < -0.05 ? 'cool' : 'neutral');
const fmtDate = s => new Date(s + 'T00:00:00').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
const charts = {};

document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t === btn));
  document.querySelectorAll('.section').forEach(s => s.classList.toggle('visible', s.id === 'tab-' + btn.dataset.tab));
}));

function setStat(id, value, sub, cls) {
  const el = document.getElementById(id);
  el.textContent = value;
  if (cls) el.className = 'stat-value ' + cls;
  if (sub !== undefined) document.getElementById(id + 'Sub').textContent = sub;
}

async function getJSON(url) {
  const res = await fetch(url);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || 'Request failed');
  return body;
}

function baseOptions(yTitle) {
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } },
               tooltip: { backgroundColor: '#1e293b', titleColor: '#e2e8f0', bodyColor: '#cbd5e1' } },
    scales: { x: { ticks: { color: TICK }, grid: { color: GRID } },
              y: { ticks: { color: TICK }, grid: { color: GRID }, title: { display: !!yTitle, text: yTitle, color: TICK } } }
  };
}

function renderSummary(s) {
  document.getElementById('badge').textContent = 'Updated daily · ' + fmtDate(s.last_date);
  document.getElementById('subtitle').textContent = s.baseline
    ? `Daily temperatures since ${s.first_date.slice(0, 4)}, compared with the ${s.baseline} normal`
    : `Daily temperatures since ${s.first_date.slice(0, 4)}`;

  const l = s.latest;
  document.getElementById('latestLabel').textContent = fmtDate(l.date);
  setStat('latest', `${l.temp_max.toFixed(1)}° / ${l.temp_min.toFixed(1)}°`,
          l.anomaly !== undefined ? fmt(l.anomaly) + ' vs normal' : 'high / low',
          l.anomaly !== undefined ? warmth(l.anomaly) : 'neutral');

  const y = s.this_year;
  document.getElementById('yearLabel').textContent = `${y.year} so far`;
  if (y.anomaly !== null) setStat('year', fmt(y.anomaly), `vs normal, over ${y.days} days`, warmth(y.anomaly));
  else setStat('year', `${y.mean_max.toFixed(1)}°`, 'average high', 'neutral');

  if (s.trend_per_decade !== null) {
    const t = s.trend_per_decade;
    setStat('trend', (t > 0 ? '+' : '') + t.toFixed(2) + '°C', 'per decade' + (s.warmest_year ? `, warmest year ${s.warmest_year.year}` : ''),
            warmth(s.trend_per_decade));
  } else setStat('trend', '—', 'needs 10+ full years of data');

  setStat('high', s.record_high.value.toFixed(1) + '°C', fmtDate(s.record_high.date));
  setStat('low', s.record_low.value.toFixed(1) + '°C', fmtDate(s.record_low.date));

  if (s.baseline) document.getElementById('footer').textContent += ` · Normal: ${s.baseline} average`;
}

function renderRecent(days) {
  const pts = key => days.map(d => ({ x: d.date, y: d[key] }));
  const datasets = [];
  if (days[0].normal_max !== undefined) {
    datasets.push(
      { label: 'Normal range', data: pts('normal_max'), borderColor: 'rgba(148,163,184,.5)', borderWidth: 1,
        pointRadius: 0, fill: false, borderDash: [4, 4] },
      { label: 'Normal low', data: pts('normal_min'), borderColor: 'rgba(148,163,184,.5)', borderWidth: 1,
        pointRadius: 0, fill: '-1', backgroundColor: 'rgba(148,163,184,.12)', borderDash: [4, 4] });
  }
  datasets.push(
    { label: 'High', data: pts('temp_max'), borderColor: '#f87171', borderWidth: 1.5, pointRadius: 0, tension: .25 },
    { label: 'Low', data: pts('temp_min'), borderColor: '#60a5fa', borderWidth: 1.5, pointRadius: 0, tension: .25 });

  const opts = baseOptions('°C');
  opts.scales.x = { type: 'time', time: { unit: 'month', tooltipFormat: 'd MMM yyyy' },
                    ticks: { color: TICK }, grid: { color: GRID } };
  opts.plugins.legend.labels.filter = item => item.text !== 'Normal low';
  charts.recent = new Chart(document.getElementById('recentChart'), { type: 'line', data: { datasets }, options: opts });
}

function stripeColor(v, alpha) {
  const t = Math.max(-1, Math.min(1, v / 1.5));   // ±1.5 °C maps to the full colour range
  const [r, g, b] = t >= 0 ? [248, 113 - 60 * t, 113 - 60 * t] : [96 + 40 * t, 165 + 30 * t, 250];
  return `rgba(${r | 0},${g | 0},${b | 0},${alpha})`;
}

function renderYears(years) {
  const withAnom = years.filter(y => y.anomaly !== null);
  if (!withAnom.length) {
    document.querySelector('#tab-years p').textContent = 'Needs at least 3 full years of data to compute normals.';
    return;
  }
  const labels = withAnom.map(y => y.complete ? String(y.year) : y.year + ' (so far)');
  const opts = baseOptions('°C vs normal');
  opts.plugins.legend.display = false;
  opts.plugins.tooltip.callbacks = { label: c => fmt(c.parsed.y) + ' vs normal' };
  charts.years = new Chart(document.getElementById('yearsChart'), {
    type: 'bar',
    data: { labels, datasets: [{ data: withAnom.map(y => y.anomaly), borderRadius: 3,
            backgroundColor: withAnom.map(y => stripeColor(y.anomaly, y.complete ? .9 : .45)) }] },
    options: opts });

  const opts2 = baseOptions('days ≥ 30 °C');
  opts2.plugins.legend.display = false;
  charts.hot = new Chart(document.getElementById('hotChart'), {
    type: 'bar',
    data: { labels: years.map(y => y.complete ? String(y.year) : y.year + ' (so far)'),
            datasets: [{ data: years.map(y => y.hot_days), backgroundColor: 'rgba(248,113,113,.75)', borderRadius: 3 }] },
    options: opts2 });
}

(async () => {
  try {
    const [summary, days, years] = await Promise.all(
      [getJSON('/api/summary'), getJSON('/api/daily?days=365'), getJSON('/api/yearly')]);
    renderSummary(summary);
    renderRecent(days);
    renderYears(years);
  } catch (e) {
    const box = document.getElementById('error');
    box.textContent = '⚠️ ' + e.message;
    box.style.display = 'block';
  }
})();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML, city=CITY_NAME, lat=CITY_LAT, lon=CITY_LON)


if __name__ == "__main__":
    # Local development server. In production use gunicorn (see run_dashboard.sh).
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)))
