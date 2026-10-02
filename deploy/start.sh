#!/bin/sh
# Starts the API (with fresh synthetic demo data) and the web app in one container.
set -e
cd /app/backend
export THODAR_DATABASE_URL=sqlite:////tmp/thodar.db
# Demo: sign-in page lists demo accounts; a fresh random signing key per start (sessions reset on restart).
export THODAR_DEMO_MODE=${THODAR_DEMO_MODE:-true}
export THODAR_SECRET_KEY=${THODAR_SECRET_KEY:-$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')}
uv run --no-sync python scripts/generate_synthetic.py --out /tmp/thodar-data >/dev/null
uv run --no-sync python scripts/seed_demo.py --data /tmp/thodar-data
uv run --no-sync uvicorn thodar.api.main:app --host 127.0.0.1 --port 8000 &
exec node /app/web/server.js
