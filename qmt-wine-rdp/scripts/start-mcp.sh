#!/usr/bin/env bash
# Launch the read-only QMT MCP server in the Wine Python.
# Auto-started by the XFCE session on RDP login (see autostart .desktop), and
# usable manually from a desktop terminal.
set -euo pipefail

# Bridge container env (token/port/path) written by the entrypoint.
if [ -f /opt/qmt-mcp/mcp.env ]; then
  set -a; . /opt/qmt-mcp/mcp.env; set +a
fi

export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
export MCP_HOST="${MCP_HOST:-0.0.0.0}"
export MCP_PORT="${MCP_PORT:-8765}"
export QMT_MINI_PATH="${QMT_MINI_PATH:-Z:\\workspace\\QMT\\extracted\\userdata_mini}"

LAUNCHER="${QMT_MCP_LAUNCHER:-/opt/qmt-mcp/qmt_mcp.py}"
PY='C:\Python312\python.exe'
LAUNCHER_WIN="$(winepath -w "$LAUNCHER" 2>/dev/null || echo "$LAUNCHER")"

echo "[start-mcp] launching $LAUNCHER_WIN on ${MCP_HOST}:${MCP_PORT}"

# Inside an RDP/XFCE session DISPLAY is set; run wine directly. Headless
# (e.g. docker exec) -> wrap in a throwaway Xvfb.
if [ -n "${DISPLAY:-}" ]; then
  exec wine "$PY" "$LAUNCHER_WIN"
else
  exec xvfb-run -a wine "$PY" "$LAUNCHER_WIN"
fi
