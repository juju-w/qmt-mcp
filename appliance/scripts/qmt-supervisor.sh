#!/usr/bin/env bash
# Session supervisor (feature 005). Launched by the XFCE autostart on RDP login.
# Keeps the MCP server running: starts start-mcp.sh and restarts it with capped
# exponential backoff if it exits. Runs INSIDE the desktop session (the MCP/QMT
# are Wine clients that need the post-login X DISPLAY), not as container PID 1.
set -uo pipefail

LOG_PREFIX="[qmt-supervisor]"
START_MCP="${QMT_START_MCP:-/usr/local/bin/start-mcp.sh}"
BACKOFF_MAX="${QMT_SUPERVISOR_BACKOFF_MAX_S:-60}"
PIDFILE="${QMT_SUPERVISOR_PIDFILE:-/tmp/qmt-supervisor.pid}"

log() { echo "${LOG_PREFIX} $*" >&2; }

# Single-instance guard: a second autostart firing must not spawn a duplicate.
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
  log "already running (pid $(cat "$PIDFILE")); exiting."
  exit 0
fi
echo "$$" > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

attempt=0
log "supervising ${START_MCP} (backoff cap ${BACKOFF_MAX}s)"
while true; do
  started=$(date +%s)
  "$START_MCP"
  code=$?
  ran=$(( $(date +%s) - started ))
  log "MCP exited code=${code} after ${ran}s"

  # A run that lasted a while is a fresh failure: reset backoff.
  if [ "$ran" -ge 60 ]; then
    attempt=0
  fi
  delay=$(( 2 ** (attempt < 6 ? attempt : 6) ))
  [ "$delay" -gt "$BACKOFF_MAX" ] && delay="$BACKOFF_MAX"
  attempt=$(( attempt + 1 ))
  log "restarting MCP in ${delay}s (attempt ${attempt})"
  sleep "$delay"
done
