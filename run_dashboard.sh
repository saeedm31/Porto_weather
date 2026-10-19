#!/bin/bash
# Start the dashboard with gunicorn (production web server).
# Settings come from .env; HOST/PORT default to 0.0.0.0:5000.
cd "$(dirname "$0")"

PY=python3
[ -x venv/bin/python ] && PY=venv/bin/python

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"

echo "🚀 Starting weather dashboard on http://$HOST:$PORT"
exec "$PY" -m gunicorn --workers 2 --bind "$HOST:$PORT" --access-logfile - dashboard:app
