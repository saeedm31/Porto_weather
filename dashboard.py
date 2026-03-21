from flask import Flask, jsonify, render_template_string
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "")

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )

@app.route("/api/data")
def api_data():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT date, temp_max, temp_min FROM porto_weather ORDER BY date ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"date": str(r[0]), "temp_max": r[1], "temp_min": r[2]} for r in rows])

@app.route("/api/yearly")
def api_yearly():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT EXTRACT(YEAR FROM date)::int AS year,
               MAX(temp_max) AS highest,
               MIN(temp_min) AS lowest
        FROM porto_weather
        GROUP BY year
        ORDER BY year ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"year": r[0], "highest": r[1], "lowest": r[2]} for r in rows])

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Porto Weather Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', sans-serif;
    background: #0a0f1e;
    color: #e2e8f0;
    min-height: 100vh;
    padding: 2rem;
  }
  h1 {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.3rem;
  }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }
  .tabs { display: flex; gap: 0.75rem; margin-bottom: 1.5rem; }
  .tab {
    padding: 0.5rem 1.25rem;
    border-radius: 9999px;
    border: 1px solid #334155;
    background: transparent;
    color: #94a3b8;
    cursor: pointer;
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    transition: all 0.2s;
  }
  .tab.active {
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    border-color: transparent;
    color: #fff;
  }
  .card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 1rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
  .stat {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 0.75rem;
    padding: 1.2rem;
    text-align: center;
  }
  .stat-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
  .stat-value { font-size: 1.75rem; font-weight: 700; }
  .stat-value.hot { color: #f87171; }
  .stat-value.cold { color: #60a5fa; }
  .stat-value.neutral { color: #a78bfa; }
  canvas { max-height: 400px; }
  .chart-section { display: none; }
  .chart-section.visible { display: block; }
  .footer { text-align: center; color: #334155; font-size: 0.78rem; margin-top: 2rem; }
  .live-badge {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: #052e16; color: #4ade80; border: 1px solid #166534;
    border-radius: 9999px; padding: 0.25rem 0.75rem; font-size: 0.78rem; font-weight: 600;
    margin-left: 1rem; vertical-align: middle;
  }
  .live-dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%;
    animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
</style>
</head>
<body>
<h1>🌡️ Porto Weather <span class="live-badge"><span class="live-dot"></span>LIVE</span></h1>
<p class="subtitle">Daily min/max temperatures — Porto, Portugal (2023 → today)</p>

<div class="stats" id="stats">
  <div class="stat"><div class="stat-label">All-time High</div><div class="stat-value hot" id="allHigh">—</div></div>
  <div class="stat"><div class="stat-label">All-time Low</div><div class="stat-value cold" id="allLow">—</div></div>
  <div class="stat"><div class="stat-label">Total Days</div><div class="stat-value neutral" id="totalDays">—</div></div>
  <div class="stat"><div class="stat-label">Last Updated</div><div class="stat-value neutral" id="lastDate" style="font-size:1rem;padding-top:0.4rem">—</div></div>
</div>

<div class="tabs">
  <button class="tab active" onclick="showTab('daily', this)">Daily History</button>
  <button class="tab" onclick="showTab('yearly', this)">Yearly Summary</button>
</div>

<div class="card">
  <div class="chart-section visible" id="tab-daily">
    <canvas id="dailyChart"></canvas>
  </div>
  <div class="chart-section" id="tab-yearly">
    <canvas id="yearlyChart"></canvas>
  </div>
</div>

<div class="footer">Data from Open-Meteo · Updates daily · Porto (41.15°N, 8.61°W)</div>

<script>
let dailyChart, yearlyChart;

function showTab(name, btn) {
  document.querySelectorAll('.chart-section').forEach(s => s.classList.remove('visible'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('visible');
  btn.classList.add('active');
}

async function loadDaily() {
  const res = await fetch('/api/data');
  const data = await res.json();
  if (!data.length) return;

  document.getElementById('allHigh').textContent = Math.max(...data.map(d => d.temp_max)).toFixed(1) + '°C';
  document.getElementById('allLow').textContent = Math.min(...data.map(d => d.temp_min)).toFixed(1) + '°C';
  document.getElementById('totalDays').textContent = data.length + ' days';
  document.getElementById('lastDate').textContent = data[data.length - 1].date;

  const ctx = document.getElementById('dailyChart').getContext('2d');
  dailyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.date),
      datasets: [
        {
          label: 'Max Temp (°C)',
          data: data.map(d => d.temp_max),
          borderColor: '#f87171',
          backgroundColor: 'rgba(248,113,113,0.08)',
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0.3
        },
        {
          label: 'Min Temp (°C)',
          data: data.map(d => d.temp_min),
          borderColor: '#60a5fa',
          backgroundColor: 'rgba(96,165,250,0.08)',
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } },
        tooltip: { backgroundColor: '#1e293b', titleColor: '#e2e8f0', bodyColor: '#94a3b8' }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'month', displayFormats: { month: 'MMM yyyy' } },
          ticks: { color: '#64748b' },
          grid: { color: '#1e293b' }
        },
        y: {
          ticks: { color: '#64748b', callback: v => v + '°C' },
          grid: { color: '#1e293b' }
        }
      }
    }
  });
}

async function loadYearly() {
  const res = await fetch('/api/yearly');
  const data = await res.json();
  if (!data.length) return;

  const ctx = document.getElementById('yearlyChart').getContext('2d');
  yearlyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.year),
      datasets: [
        {
          label: 'Yearly High (°C)',
          data: data.map(d => d.highest),
          backgroundColor: 'rgba(248,113,113,0.7)',
          borderColor: '#f87171',
          borderWidth: 1.5,
          borderRadius: 6
        },
        {
          label: 'Yearly Low (°C)',
          data: data.map(d => d.lowest),
          backgroundColor: 'rgba(96,165,250,0.7)',
          borderColor: '#60a5fa',
          borderWidth: 1.5,
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } },
        tooltip: { backgroundColor: '#1e293b', titleColor: '#e2e8f0', bodyColor: '#94a3b8' }
      },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
        y: {
          ticks: { color: '#64748b', callback: v => v + '°C' },
          grid: { color: '#1e293b' }
        }
      }
    }
  });
}

loadDaily();
loadYearly();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
