#!/usr/bin/env bash
# Smoke-test the Wine Python + the broker pack's xtquant (resolved by detect-broker).
set -euo pipefail

if [ -f /opt/qmt-mcp/mcp.env ]; then
  set -a; . /opt/qmt-mcp/mcp.env; set +a
fi

export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
PY="${PY_WIN_DIR:-C:\\Python312}\\python.exe"
XTQ_DIR_WIN="${QMT_XTQUANT_DIR_WIN:-}"

run() { if [ -n "${DISPLAY:-}" ]; then wine "$@"; else xvfb-run -a wine "$@"; fi; }

echo "== python version =="
run "$PY" --version

echo "== xtquant imports (from broker pack: ${XTQ_DIR_WIN:-<unset>}) =="
run "$PY" -c "import os,sys; d=os.environ.get('QMT_XTQUANT_DIR_WIN','').strip();
sys.path.insert(0, d) if d else None;
import xtquant, xtquant.xtdata, xtquant.xttrader, xtquant.xtdatacenter;
print('xtquant import OK:', xtquant.__file__)"
