#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "==> Installing dependencies..."
pip3 install -r backend/requirements.txt
cd frontend && npm install && cd ..

echo "==> Resetting database..."
PYTHONPATH=. python3 -c "from backend.database import reset_db; reset_db()"

echo "==> Starting backend on :8000 ..."
PYTHONPATH=. uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "==> Starting frontend on :5173 ..."
( cd frontend && npm run dev ) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

sleep 2
open http://localhost:5173 2>/dev/null || xdg-open http://localhost:5173 2>/dev/null || true

echo "Backend PID: $BACKEND_PID  Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both."
wait
