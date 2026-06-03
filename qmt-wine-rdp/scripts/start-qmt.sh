#!/usr/bin/env bash
# Launch the broker's QMT client resolved by detect-broker (from the mounted pack).
set -euo pipefail

# Resolved broker config (client path etc.), bridged by the entrypoint.
if [ -f /opt/qmt-mcp/mcp.env ]; then
  set -a; . /opt/qmt-mcp/mcp.env; set +a
fi

export DISPLAY="${DISPLAY:-:10}"
if [ -z "${XAUTHORITY:-}" ] && [ -f "$HOME/.Xauthority" ]; then
  export XAUTHORITY="$HOME/.Xauthority"
fi
export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
export QT_OPENGL="${QT_OPENGL:-software}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export QTWEBENGINE_DISABLE_SANDBOX="${QTWEBENGINE_DISABLE_SANDBOX:-1}"

# Self-heal the Wine prefix once per container boot: a baked prefix can come up
# without a usable display driver ("nodrv_CreateWindow: no driver could be
# loaded") until `wineboot -u` runs. /tmp is fresh each container start, so the
# marker makes this run exactly once per boot.
if [ ! -f /tmp/.wine-healed ]; then
  echo "[start-qmt] healing wine prefix (wineboot -u)..."
  wineboot -u >/dev/null 2>&1 || true
  wineserver -w 2>/dev/null || true
  touch /tmp/.wine-healed
fi

# Launch via the resolved Linux path — Wine accepts unix paths and this avoids
# any backslash-escaping pitfalls. Fall back to the Wine path if unset.
CLIENT="${QMT_CLIENT:-}"
BIN_DIR="${QMT_BIN_DIR:-/broker}"
: "${CLIENT:?detect-broker did not resolve a client; check the broker pack}"

echo "[start-qmt] broker=${QMT_BROKER_ID:-?} client=$CLIENT"
cd "$BIN_DIR"
exec wine "$CLIENT"
