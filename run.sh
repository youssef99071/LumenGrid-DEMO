#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== LumenGrid ==="

cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

cd "$ROOT/frontend"
npm install --silent
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "  Dashboard -> http://localhost:5173"
echo "  API docs  -> http://localhost:8000/docs"
echo "  Ctrl+C to stop"
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM
wait
