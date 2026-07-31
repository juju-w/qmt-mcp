#!/usr/bin/env bash
# PID 1 for persistent desktop mode. The base entrypoint starts xrdp/sesman,
# then this process creates and monitors the one long-lived Xorg/XFCE session.
set -euo pipefail

LOG_PREFIX="[persistent-desktop]"
STATUS_FILE="${QMT_DESKTOP_STATUS_FILE:-/run/qmt/desktop/status.json}"
SESRUN_BIN="${XRDP_SESRUN_BIN:-/usr/bin/xrdp-sesrun}"
USER_NAME="${USER_NAME:-wineuser}"
GEOMETRY="${QMT_RDP_GEOMETRY:-1440x900x32}"
BOOT_RETRIES="${QMT_RDP_BOOT_RETRIES:-3}"
BOOT_BACKOFF="${QMT_RDP_BOOT_BACKOFF_S:-2}"
MONITOR_INTERVAL="${QMT_DESKTOP_MONITOR_INTERVAL_S:-2}"
# Upstream 0.10 writes these directly below /run. The Wine base's historical
# entrypoint still probes /run/xrdp/*, so do not inherit those 0.9-era paths.
XRDP_PIDFILE="${XRDP_PIDFILE:-/run/xrdp.pid}"
SESMAN_PIDFILE="${XRDP_SESMAN_PIDFILE:-/run/xrdp-sesman.pid}"

display_number=""
xorg_pid=""
stopping=0
last_mcp_ready=""

log() { printf '%s %s\n' "$LOG_PREFIX" "$*" >&2; }

write_status() {
  local state="$1" mcp_ready="${2:-false}" tmp display_json="null" pid_json="null"
  [ -z "$display_number" ] || display_json="\":${display_number}\""
  [ -z "$xorg_pid" ] || pid_json="$xorg_pid"
  install -d -m 0755 "$(dirname "$STATUS_FILE")"
  tmp="${STATUS_FILE}.new"
  printf '{"schema_version":1,"mode":"persistent","state":"%s","display":%s,"xorg_pid":%s,"mcp_ready":%s,"updated_at":"%s"}\n' \
    "$state" "$display_json" "$pid_json" "$mcp_ready" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$tmp"
  mv "$tmp" "$STATUS_FILE"
  chmod 0644 "$STATUS_FILE"
}

read_secret() {
  local secret=""
  if [ -n "${QMT_RDP_PASSWORD_FILE:-}" ]; then
    [ -r "$QMT_RDP_PASSWORD_FILE" ] || {
      log "ERROR: QMT_RDP_PASSWORD_FILE is not readable"
      return 1
    }
    IFS= read -r secret < "$QMT_RDP_PASSWORD_FILE" || [ -n "$secret" ]
  else
    secret="${QMT_RDP_PASSWORD:-}"
  fi
  printf '%s' "$secret"
}

pidfile_alive() {
  local file="$1" pid
  [ -r "$file" ] || return 1
  pid="$(cat "$file")"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

find_xorg_pid() {
  pgrep -f "(^|/)Xorg :${display_number}([^0-9]|$)" | head -n 1
}

desktop_alive() {
  [ -n "$xorg_pid" ] && kill -0 "$xorg_pid" 2>/dev/null
}

mcp_alive() {
  curl -fsS --max-time 2 "http://127.0.0.1:${MCP_PORT:-8765}/livez" >/dev/null 2>&1
}

shutdown_desktop() {
  [ "$stopping" -eq 0 ] || return
  stopping=1
  trap - TERM INT
  write_status stopping false
  log "stopping persistent desktop"

  if [ -n "$xorg_pid" ] && kill -0 "$xorg_pid" 2>/dev/null; then
    kill -TERM "$xorg_pid" 2>/dev/null || true
  fi
  gosu "$USER_NAME" env WINEPREFIX="${WINEPREFIX:-/home/${USER_NAME}/.wine}" wineserver -k >/dev/null 2>&1 || true

  for file in "$XRDP_PIDFILE" "$SESMAN_PIDFILE"; do
    if [ -r "$file" ]; then
      kill -TERM "$(cat "$file")" 2>/dev/null || true
    fi
  done
  exit 0
}

if [[ "$GEOMETRY" =~ ^([0-9]+)x([0-9]+)(x([0-9]+))?$ ]]; then
  SESSION_GEOMETRY="${BASH_REMATCH[1]}x${BASH_REMATCH[2]}"
  SESSION_BPP="${BASH_REMATCH[4]:-32}"
else
  log "ERROR: QMT_RDP_GEOMETRY must use WIDTHxHEIGHT or WIDTHxHEIGHTxBPP"
  exit 2
fi
case "$BOOT_RETRIES:$BOOT_BACKOFF" in
  *[!0-9:]* | :* | *:) log "ERROR: desktop retry settings must be non-negative integers"; exit 2 ;;
esac
[ "$BOOT_RETRIES" -le 10 ] || { log "ERROR: QMT_RDP_BOOT_RETRIES must be <= 10"; exit 2; }
[ "$BOOT_BACKOFF" -ge 1 ] && [ "$BOOT_BACKOFF" -le 60 ] || {
  log "ERROR: QMT_RDP_BOOT_BACKOFF_S must be between 1 and 60"
  exit 2
}

trap shutdown_desktop TERM INT
write_status starting false

password="$(read_secret)" || {
  write_status failed false
  exit 3
}
[ -n "$password" ] || {
  log "ERROR: persistent mode requires QMT_RDP_PASSWORD_FILE or QMT_RDP_PASSWORD"
  write_status failed false
  exit 3
}

attempt=1
max_attempts=$((BOOT_RETRIES + 1))
while [ "$attempt" -le "$max_attempts" ]; do
  log "creating Xorg session (attempt ${attempt}/${max_attempts}, geometry ${SESSION_GEOMETRY}x${SESSION_BPP})"
  if output="$(printf '%s\n' "$password" | "$SESRUN_BIN" -g "$SESSION_GEOMETRY" -b "$SESSION_BPP" -t Xorg -F 0 "$USER_NAME" 2>&1)"; then
    display_number="$(printf '%s\n' "$output" | sed -n 's/.*display=:\([0-9][0-9]*\).*/\1/p' | tail -n 1)"
    if [ -n "$display_number" ]; then
      break
    fi
    log "session launcher returned success without a display"
  else
    log "session launcher failed (attempt ${attempt})"
  fi
  attempt=$((attempt + 1))
  [ "$attempt" -gt "$max_attempts" ] || sleep "$BOOT_BACKOFF"
done
unset password QMT_RDP_PASSWORD

if [ -z "$display_number" ]; then
  log "ERROR: unable to create the persistent desktop after ${max_attempts} attempt(s)"
  write_status failed false
  exit 4
fi

for _ in $(seq 1 30); do
  xorg_pid="$(find_xorg_pid || true)"
  [ -z "$xorg_pid" ] || break
  sleep 1
done
if [ -z "$xorg_pid" ]; then
  log "ERROR: session :${display_number} did not start Xorg"
  write_status failed false
  exit 5
fi

log "desktop ready on :${display_number} (Xorg pid ${xorg_pid}); RDP clients will reconnect to it"
write_status ready false

while true; do
  if ! pidfile_alive "$XRDP_PIDFILE"; then
    log "ERROR: xrdp exited"
    write_status failed false
    exit 6
  fi
  if ! pidfile_alive "$SESMAN_PIDFILE"; then
    log "ERROR: xrdp-sesman exited"
    write_status failed false
    exit 7
  fi
  if ! desktop_alive; then
    log "ERROR: persistent Xorg session exited"
    write_status failed false
    exit 8
  fi

  if mcp_alive; then
    if [ "$last_mcp_ready" != true ]; then
      write_status ready true
      last_mcp_ready=true
    fi
  elif [ "$last_mcp_ready" != false ]; then
    write_status ready false
    last_mcp_ready=false
  fi
  sleep "$MONITOR_INTERVAL"
done
