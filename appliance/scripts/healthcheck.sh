#!/usr/bin/env bash
# Container HEALTHCHECK (feature 005). Probes the unauthenticated /livez endpoint
# — no bearer token needed, and it discloses only liveness. Non-zero exit => the
# orchestrator marks the container unhealthy.
set -euo pipefail

PORT="${MCP_PORT:-8765}"
URL="http://127.0.0.1:${PORT}/livez"

# -f: non-2xx -> non-zero exit. Short timeouts so a wedged app fails fast.
curl -fsS --max-time 5 "$URL" >/dev/null
