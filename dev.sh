#!/usr/bin/env bash
# Starts the API (port 8000) and the web app (port 3000). Ctrl+C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

if [ ! -f "$ROOT/api/.env" ]; then
  echo "Missing api/.env. Copy api/.env.example to api/.env and add your ANTHROPIC_API_KEY." >&2
  exit 1
fi

trap 'kill 0' EXIT
(cd "$ROOT/api" && .venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app) &
(cd "$ROOT/web" && npm run dev -- --port 3000) &
wait
