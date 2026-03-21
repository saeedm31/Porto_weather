#!/bin/bash
# Start the Porto weather dashboard on port 5000
cd "$(dirname "$0")"

# Load environment variables if .env exists
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

echo "🚀 Starting Porto Weather Dashboard on http://127.0.0.1:5000"
python3 dashboard.py
