#!/usr/bin/env bash
# Run LumenGrid backend (works without system venv/pip).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}/.vendor:${PYTHONPATH:-}"
cd "$ROOT"
exec python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
