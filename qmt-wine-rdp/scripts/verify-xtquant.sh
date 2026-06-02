#!/usr/bin/env bash
# Smoke-test the baked Windows Python + xtquant inside the Wine prefix.
set -euo pipefail

export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
PY="${PY_WIN_DIR:-C:\\Python312}\\python.exe"

run() { if [ -n "${DISPLAY:-}" ]; then wine "$@"; else xvfb-run -a wine "$@"; fi; }

echo "== python version =="
run "$PY" --version

echo "== xtquant imports =="
run "$PY" -c "import xtquant, xtquant.xtdata, xtquant.xttrader, xtquant.xtdatacenter; print('xtquant import OK:', xtquant.__file__)"
