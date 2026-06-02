#!/usr/bin/env bash
# Launch the broker's QMT client resolved by detect-broker (from the mounted pack).
set -euo pipefail

# Resolved broker config (client path etc.), bridged by the entrypoint.
if [ -f /opt/qmt-mcp/mcp.env ]; then
  set -a; . /opt/qmt-mcp/mcp.env; set +a
fi

export DISPLAY="${DISPLAY:-:10}"
export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
export QT_OPENGL="${QT_OPENGL:-software}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export QTWEBENGINE_DISABLE_SANDBOX="${QTWEBENGINE_DISABLE_SANDBOX:-1}"

# Launch via the resolved Linux path — Wine accepts unix paths and this avoids
# any backslash-escaping pitfalls. Fall back to the Wine path if unset.
CLIENT="${QMT_CLIENT:-}"
BIN_DIR="${QMT_BIN_DIR:-/broker}"
: "${CLIENT:?detect-broker did not resolve a client; check the broker pack}"

echo "[start-qmt] broker=${QMT_BROKER_ID:-?} client=$CLIENT"
cd "$BIN_DIR"
exec wine "$CLIENT"
