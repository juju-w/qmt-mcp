#!/usr/bin/env bash
# Verify a deployed QMT-MCP endpoint: liveness, auth enforcement, MCP handshake,
# tool count, and qmt_health. Read-only — calls no market-data or account tools.
#
#   QMT_MCP_ACCESS_TOKEN=... ./verify-mcp.sh <base-url>
#   QMT_MCP_TOKEN=... ./verify-mcp.sh <base-url>
#   ./verify-mcp.sh http://127.0.0.1:38765
#
# Exit 0 = all checks passed. Non-zero = at least one failed (usable as a deploy gate).
set -uo pipefail

usage() {
  printf 'usage: QMT_MCP_ACCESS_TOKEN=... %s <base-url>\n' "${0##*/}" >&2
  printf '   or: QMT_MCP_TOKEN=... %s <base-url>\n' "${0##*/}" >&2
  printf '       %s http://127.0.0.1:38765  # prompts in a terminal\n' "${0##*/}" >&2
  exit 2
}

[ "$#" -eq 1 ] || usage
BASE="$1"
BASE="${BASE%/}"
TOKEN="${QMT_MCP_ACCESS_TOKEN:-${QMT_MCP_TOKEN:-}}"
MIN_TOOLS="${QMT_MCP_MIN_TOOLS:-37}"

if [ -z "$TOKEN" ] && [ -t 0 ]; then
  read -r -s -p "QMT MCP token: " TOKEN
  printf '\n'
fi
if [ -z "$TOKEN" ]; then
  printf 'verify-mcp: set QMT_MCP_ACCESS_TOKEN or QMT_MCP_TOKEN, or run interactively to enter the token.\n' >&2
  exit 2
fi
if [[ ! "$MIN_TOOLS" =~ ^[1-9][0-9]*$ ]]; then
  printf 'verify-mcp: QMT_MCP_MIN_TOOLS must be a positive integer.\n' >&2
  exit 2
fi
if [[ "$BASE" == http://* ]] &&
   [[ ! "$BASE" =~ ^http://(127\.0\.0\.1|localhost|\[::1\])(:[0-9]+)?(/|$) ]] &&
   [ "${QMT_MCP_ALLOW_INSECURE_HTTP:-0}" != "1" ]; then
  printf 'verify-mcp: refusing remote plain HTTP; use HTTPS or an SSH tunnel to localhost.\n' >&2
  printf 'verify-mcp: set QMT_MCP_ALLOW_INSECURE_HTTP=1 only on a controlled private network.\n' >&2
  exit 2
fi

ACCEPT='application/json, text/event-stream'
HDR="$(mktemp)"; trap 'rm -f "$HDR"' EXIT
fail=0
ok()  { printf '  [ok]   %s\n' "$1"; }
err() { printf '  [FAIL] %s\n' "$1"; fail=$((fail + 1)); }

echo "verify-mcp: ${BASE}"

# 1) /livez is unauthenticated and discloses only liveness.
if curl -fsS --max-time 5 "${BASE}/livez" 2>/dev/null | grep -q '"ok": *true'; then
  ok "/livez reports live."
else
  err "/livez unreachable. Inspect container logs and /run/qmt/desktop/status.json."
  printf '         In QMT_DESKTOP_MODE=manual, connect RDP once to start XFCE autostart.\n'
  echo "verify-mcp: ${fail} failure(s) — aborting (nothing listening)."
  exit 1
fi

# 2) An unauthenticated tool call MUST be rejected.
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST "${BASE}/mcp" \
        -H 'Content-Type: application/json' -H "Accept: ${ACCEPT}" -d '{}' 2>/dev/null)"
if [ "$code" = "401" ]; then
  ok "unauthenticated /mcp rejected (401)."
else
  err "unauthenticated /mcp returned ${code}, expected 401 — endpoint may be open."
fi

# 3) MCP handshake. The session id comes back as a response header.
curl -s --max-time 20 -D "$HDR" -o /dev/null -X POST "${BASE}/mcp" \
  -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
  -H "Accept: ${ACCEPT}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"verify-mcp","version":"1"}}}' \
  2>/dev/null
SESSION="$(grep -i '^mcp-session-id' "$HDR" | tr -d '\r' | cut -d' ' -f2)"
if [ -n "$SESSION" ]; then
  ok "initialize handshake succeeded."
else
  err "initialize returned no mcp-session-id — bad token, or not an MCP endpoint."
  echo "verify-mcp: ${fail} failure(s)."
  exit 1
fi

call() {  # call <json-body> — authenticated, session-bound POST
  curl -s --max-time 60 -X POST "${BASE}/mcp" \
    -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
    -H "Accept: ${ACCEPT}" -H "mcp-session-id: ${SESSION}" -d "$1" 2>/dev/null
}

call '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null

# 4) Tool registry. The standard readonly appliance registers 37 tools.
tools="$(call '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
         | grep -o '"name":"qmt_[a-z0-9_]*"' | sort -u | wc -l | tr -d ' ')"
if [ "${tools:-0}" -ge "$MIN_TOOLS" ]; then
  ok "tools/list returned ${tools} tools."
else
  err "tools/list returned only ${tools:-0} tools; expected at least ${MIN_TOOLS}."
fi

# 5) qmt_health. Parsed from the SSE data: line without assuming a JSON parser exists.
health="$(call '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"qmt_health","arguments":{}}}')"
field() { printf '%s' "$health" | grep -o "\"$1\":\"[a-z_]*\"" | head -1 | cut -d'"' -f4; }

if printf '%s' "$health" | grep -q '"ok":true'; then
  ok "qmt_health ok (broker_config=$(field broker_config), xtquant_import=$(field xtquant_import), audit=$(field audit))."
else
  err "qmt_health did not report ok=true."
fi

# A missing broker configuration means the image cannot start the terminal reliably.
case "$(field broker_config)" in
  loaded) ok "broker configuration loaded." ;;
  "")     err "could not read broker_config from qmt_health." ;;
  *)      err "broker_config=$(field broker_config) — broker pack configuration is incomplete." ;;
esac

# xtquant must import — that validates the broker pack itself.
case "$(field xtquant_import)" in
  ok) ok "xtquant imports under Wine (broker pack valid)." ;;
  "") err "could not read xtquant_import from qmt_health." ;;
  *)  err "xtquant_import=$(field xtquant_import) — broker pack xtquant is unusable." ;;
esac

# Login-dependent states are acceptable before the terminal session is established.
# Registration/configuration failures are deploy failures even when qmt_health.ok is true.
xtdata="$(field xtdata)"
case "$xtdata" in
  ready)
    ok "xtdata ready."
    ;;
  awaiting_login|degraded|not_ready)
    printf '  [info] xtdata=%s, xttrade=%s — expected until the QMT terminal is\n' \
           "$xtdata" "$(field xttrade)"
    printf '         logged in over RDP. Not a deployment fault.\n'
    ;;
  "")
    err "could not read xtdata from qmt_health."
    ;;
  error|disabled)
    err "xtdata=${xtdata} — standard readonly market-data tools are unavailable."
    ;;
  *)
    err "xtdata=${xtdata} — unexpected readiness state."
    ;;
esac

echo "verify-mcp: ${fail} failure(s)."
[ "$fail" -eq 0 ] || { echo "verify-mcp: FAILED."; exit 1; }
echo "verify-mcp: PASSED."
