#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
command -v python3 >/dev/null || { echo "Python 3 is required."; exit 1; }
command -v npm >/dev/null || { echo "npm is required."; exit 1; }
cd "$ROOT/backend"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
pip install -r requirements.txt
cd "$ROOT/frontend"
npm install --cache "${TMPDIR:-/tmp}/atlas-npm-cache"
echo "ATLAS frontend: http://localhost:5173"
echo "ATLAS backend:  http://localhost:8000"
echo "API docs:       http://localhost:8000/docs"
(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --reload --port "${BACKEND_PORT:-8000}") &
trap 'kill 0' EXIT
npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT:-5173}"
