#!/usr/bin/env bash
# Verify a deployed QMT-MCP endpoint: liveness, auth enforcement, MCP handshake,
# tool count, and qmt_health. Read-only — calls no market-data or account tools.
#
#   ./verify-mcp.sh <base-url> <token>
#   ./verify-mcp.sh http://127.0.0.1:38765 "$QMT_MCP_TOKEN"
#
# Exit 0 = all checks passed. Non-zero = at least one failed (usable as a deploy gate).
set -uo pipefail

BASE="${1:?usage: verify-mcp.sh <base-url> <token>   e.g. http://127.0.0.1:38765}"
TOKEN="${2:?missing bearer token}"
BASE="${BASE%/}"

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
  err "/livez unreachable. MCP starts on RDP desktop login — start the supervisor:"
  printf '         docker exec -u wineuser -d <container> bash -lc "nohup /usr/local/bin/qmt-supervisor.sh > /tmp/sup.log 2>&1"\n'
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

# 4) Tool registry. A readonly appliance registers ~37 tools; xtdata alone is ~35.
tools="$(call '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
         | grep -o '"name":"qmt_[a-z_]*"' | sort -u | wc -l | tr -d ' ')"
if [ "${tools:-0}" -ge 10 ]; then
  ok "tools/list returned ${tools} tools."
else
  err "tools/list returned only ${tools:-0} tools — registration likely failed."
fi

# 5) qmt_health. Parsed from the SSE data: line without assuming a JSON parser exists.
health="$(call '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"qmt_health","arguments":{}}}')"
field() { printf '%s' "$health" | grep -o "\"$1\":\"[a-z_]*\"" | head -1 | cut -d'"' -f4; }

if printf '%s' "$health" | grep -q '"ok":true'; then
  ok "qmt_health ok (broker_config=$(field broker_config), xtquant_import=$(field xtquant_import), audit=$(field audit))."
else
  err "qmt_health did not report ok=true."
fi

# xtquant must import — that validates the broker pack itself.
case "$(field xtquant_import)" in
  ok) ok "xtquant imports under Wine (broker pack valid)." ;;
  "") err "could not read xtquant_import from qmt_health." ;;
  *)  err "xtquant_import=$(field xtquant_import) — broker pack xtquant is unusable." ;;
esac

# xtdata/xttrade state is informational: both stay degraded until the QMT terminal
# itself is logged in over RDP. Never a deploy failure.
xtdata="$(field xtdata)"
if [ "$xtdata" = "ok" ]; then
  ok "xtdata ready."
else
  printf '  [info] xtdata=%s, xttrade=%s — expected until the QMT terminal is\n' \
         "${xtdata:-unknown}" "$(field xttrade)"
  printf '         logged in over RDP. Not a deployment fault.\n'
fi

echo "verify-mcp: ${fail} failure(s)."
[ "$fail" -eq 0 ] || { echo "verify-mcp: FAILED."; exit 1; }
echo "verify-mcp: PASSED."
