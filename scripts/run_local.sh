#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8010}"

cd "$ROOT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[setup] Creating project virtual environment at $ROOT_DIR/.venv"
  python3 -m venv "$ROOT_DIR/.venv"
fi

if ! "$PYTHON_BIN" -c "import uvicorn, numpy, openai" >/dev/null 2>&1; then
  echo "[setup] Installing required packages"
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt"
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "[error] OPENAI_API_KEY is not set"
  echo "Run: export OPENAI_API_KEY='YOUR_NEW_KEY_HERE'"
  exit 1
fi

echo "[run] Building index artifacts"
"$PYTHON_BIN" "$ROOT_DIR/scripts/process_data.py"

echo "[run] Starting API at http://$HOST:$PORT/ui"
exec "$PYTHON_BIN" -m uvicorn --app-dir "$ROOT_DIR" app.main:app --host "$HOST" --port "$PORT" --reload
