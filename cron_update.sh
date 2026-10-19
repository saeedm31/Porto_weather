#!/bin/bash
# Daily update, meant for cron. Fetches the latest days into the database.
# Uses the project's virtual environment if there is one, and logs to ./logs/fetch.log.
cd "$(dirname "$0")"

PY=python3
[ -x venv/bin/python ] && PY=venv/bin/python

mkdir -p logs
{
  echo "--- $(date '+%Y-%m-%d %H:%M:%S')"
  "$PY" fetch_weather.py
} >> logs/fetch.log 2>&1
