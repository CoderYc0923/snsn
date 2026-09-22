#!/usr/bin/env bash
# SnSn local API — thin wrapper around `python -m app.cli dev`
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "[snsn] missing .venv — run: make install"
  echo "  or: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e ."
  exit 1
fi

exec .venv/bin/python -m app.cli dev "$@"
