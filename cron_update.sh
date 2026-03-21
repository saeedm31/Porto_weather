#!/bin/bash
# Daily cron updater for Porto weather data
# Runs: fetch_weather.py (upserts last 7 days)

cd "$(dirname "$0")"

# Load environment variables if .env exists
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

/usr/bin/python3 fetch_weather.py >> /var/log/porto-weather.log 2>&1
