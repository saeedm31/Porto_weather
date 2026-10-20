# 🌡️ City Climate Dashboard

**Is today unusually warm? A self-hosted dashboard that tracks your city's daily temperatures and compares them with the 30-year climate normal.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Web-Flask-000000?logo=flask)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white)](#-option-1-docker-compose-any-server)
[![Tests](https://github.com/saeedm31/Porto_weather/actions/workflows/tests.yml/badge.svg)](https://github.com/saeedm31/Porto_weather/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Set up for Porto, Portugal by default, and works for any city: change four settings and redeploy.

---

## 💡 What it shows

A weather app tells you today's temperature. This dashboard tells you **what it means**:

- **Latest day vs normal**: for example "24.1° / 15.2°, +2.3 °C warmer than normal for this date"
- **This year so far**: how much warmer or colder than normal the year has been, comparing each day with the normal *for that date*, so a half-finished year isn't skewed by missing winter months
- **Warming trend**: the long-term trend in °C per decade, and the warmest year on record
- **Record high and low**, with dates
- **Charts**:
  - the last 12 months against the normal range
  - every year since 1991 as warm or cold bars (in the style of the "warming stripes")
  - hot days (30 °C or more) per year

The "normal" is the **1991–2020 average** for each calendar day, the current World Meteorological Organization standard. The daily averages are smoothed over a 31-day window.

## 🧠 How it works

```
Open-Meteo archive API ──► fetch_weather.py ──► PostgreSQL ──► dashboard.py (Flask) ──► browser (Chart.js)
   (free, no API key)       daily, upsert        1 row/day       climate.py analysis
```

| File | What it does |
|---|---|
| `fetch_weather.py` | Downloads daily min/max temperatures. First run backfills from 1991 in 5-year chunks; daily runs re-fetch the last week to catch late corrections. Idempotent (upserts by date). |
| `climate.py` | The analysis: daily normals, anomalies, yearly summary, warming trend. Pure Python, no database needed, fully unit-tested. |
| `dashboard.py` | Flask app with a JSON API and the dashboard page. Results are cached for 10 minutes. |
| `db.py` | Settings (from `.env`) and database helpers, shared by everything else. |
| `setup_db.py` | Creates the table. |

**API**

| Endpoint | Returns |
|---|---|
| `/api/summary` | Headline numbers: latest day, this year, trend, records |
| `/api/daily?days=365` | Daily highs and lows with the normal for each day |
| `/api/yearly` | One row per year: averages, extremes, hot days, anomaly |
| `/health` | Database status and date of the latest data, for uptime checks |

## 🚀 Run it on your own server

### Option 1: Docker Compose (any server)

Needs [Docker](https://docs.docker.com/engine/install/). Runs the database, the daily updater and the dashboard:

```bash
git clone https://github.com/saeedm31/Porto_weather.git
cd Porto_weather
cp .env.example .env        # set DB_PASS, and your city if not Porto
docker compose up -d --build
```

Open `http://<your-server-ip>:5000`. On first start the updater downloads the full history, which takes about a minute.

### Option 2: Ubuntu server, e.g. AWS EC2 with RDS

<details>
<summary>Step-by-step guide</summary>

**1. Database.** Use PostgreSQL on the same machine (`sudo apt install postgresql`) or a managed one such as AWS RDS. With RDS, allow port 5432 from your server's security group and note the endpoint.

**2. Server.** On an Ubuntu machine (for EC2: allow SSH 22 and TCP 5000 in the security group):

```bash
sudo apt update && sudo apt install -y python3 python3-venv git
git clone https://github.com/saeedm31/Porto_weather.git
cd Porto_weather
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env      # database details and city
```

**3. Create the table and load the history**

```bash
venv/bin/python setup_db.py
venv/bin/python fetch_weather.py
```

**4. Start the dashboard as a service** (restarts on crash and reboot):

```bash
sudo cp deploy/weather-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weather-dashboard
```

Open `http://<your-server-ip>:5000`. For a domain name and HTTPS, put nginx or Caddy in front of port 5000.

**5. Daily updates.** Run `crontab -e` and add:

```text
0 6 * * * /bin/bash /home/ubuntu/Porto_weather/cron_update.sh
```

The script uses the project's virtual environment and logs to `logs/fetch.log`.

</details>

### Option 3: Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # point DB_* at a local PostgreSQL
python setup_db.py && python fetch_weather.py
python dashboard.py                # http://127.0.0.1:5000
```

## 🌍 Use another city

Set these four values in `.env`, then run `fetch_weather.py` again (or restart Docker Compose):

```env
CITY_NAME=Lisbon
CITY_LAT=38.72
CITY_LON=-9.14
TIMEZONE=Europe/Lisbon
```

Use a fresh database or set `WEATHER_TABLE` to a new table name, so the two cities' data don't mix.

## ✅ Tests

```bash
python -m unittest
```

They run on every push (GitHub Actions). 18 tests cover the climate analysis (normals, anomalies for partial years, trend detection, missing data) and the fetch planning (backfill, daily refresh, filling early years for an existing database).

## 🗺️ Ideas

- Precipitation and "days without rain"
- Compare several cities side by side
- Email or Telegram alert on record days

---

Built by [Saeed Hojjatpanah](https://github.com/saeedm31). Weather data: [Open-Meteo](https://open-meteo.com/) historical weather API (CC BY 4.0).
