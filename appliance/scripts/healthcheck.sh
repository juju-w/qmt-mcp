#!/usr/bin/env bash
# Container HEALTHCHECK (feature 005). Probes the unauthenticated /livez endpoint
# — no bearer token needed, and it discloses only liveness. Non-zero exit => the
# orchestrator marks the container unhealthy.
set -euo pipefail

PORT="${MCP_PORT:-8765}"
URL="http://127.0.0.1:${PORT}/livez"

if [ "${QMT_DESKTOP_MODE:-manual}" = "persistent" ]; then
  STATUS_FILE="${QMT_DESKTOP_STATUS_FILE:-/run/qmt/desktop/status.json}"
  XORG_PID="$(python3 - "$STATUS_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    status = json.load(handle)
if status.get("state") != "ready" or not isinstance(status.get("xorg_pid"), int):
    raise SystemExit(1)
print(status["xorg_pid"])
PY
)"
  kill -0 "$XORG_PID" 2>/dev/null
fi

# -f: non-2xx -> non-zero exit. Short timeouts so a wedged app fails fast.
curl -fsS --max-time 5 "$URL" >/dev/null
