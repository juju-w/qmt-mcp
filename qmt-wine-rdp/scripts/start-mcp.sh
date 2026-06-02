#!/usr/bin/env bash
# Launch the read-only QMT MCP server in the Wine Python.
# Auto-started by the XFCE session on RDP login (autostart .desktop); also usable
# manually from a desktop terminal. Reads broker config resolved by detect-broker.
set -euo pipefail

# Bridged container + resolved-broker env (token/port/xtquant/userdata paths).
if [ -f /opt/qmt-mcp/mcp.env ]; then
  set -a; . /opt/qmt-mcp/mcp.env; set +a
fi

export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
export MCP_HOST="${MCP_HOST:-0.0.0.0}"
export MCP_PORT="${MCP_PORT:-8765}"

# Resolved by detect-broker (Wine paths). The launcher consumes these.
export QMT_XTQUANT_DIR_WIN="${QMT_XTQUANT_DIR_WIN:-}"
export QMT_USERDATA_WIN="${QMT_USERDATA_WIN:-}"
export QMT_MCP_MODE="${QMT_MCP_MODE:-readonly}"

LAUNCHER="${QMT_MCP_LAUNCHER:-/opt/qmt-mcp/qmt_mcp.py}"
PY='C:\Python312\python.exe'
LAUNCHER_WIN="$(winepath -w "$LAUNCHER" 2>/dev/null || echo "$LAUNCHER")"

echo "[start-mcp] broker=${QMT_BROKER_ID:-?} mode=${QMT_MCP_MODE} on ${MCP_HOST}:${MCP_PORT}"
echo "[start-mcp] xtquant=${QMT_XTQUANT_DIR_WIN:-<unset>} userdata=${QMT_USERDATA_WIN:-<unset>}"

if [ -n "${DISPLAY:-}" ]; then
  exec wine "$PY" "$LAUNCHER_WIN"
else
  exec xvfb-run -a wine "$PY" "$LAUNCHER_WIN"
fi
