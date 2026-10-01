#!/bin/sh
# Starts the API (with fresh synthetic demo data) and the web app in one container.
set -e
cd /app/backend
uv run --no-sync python scripts/generate_synthetic.py --out /tmp/thodar-data >/dev/null
THODAR_DATABASE_URL=sqlite:////tmp/thodar.db uv run --no-sync python scripts/seed_demo.py --data /tmp/thodar-data
THODAR_DATABASE_URL=sqlite:////tmp/thodar.db uv run --no-sync uvicorn thodar.api.main:app --host 127.0.0.1 --port 8000 &
exec node /app/web/server.js
