#!/usr/bin/env bash
# Headless VNC session (QMT_DISPLAY_MODE=vnc|both).
#
# Why this exists: in the default `rdp` mode the QMT terminal and the MCP are
# launched by the XFCE autostart, which only fires when an operator logs in over
# RDP. That makes "MCP serving" depend on a human opening a desktop, and anything
# started via `docker exec` is not a child of PID 1 (so it dies with the exec
# session). This script instead owns the whole graphical stack as a child of the
# container entrypoint:
#
#   Xvfb (virtual screen) -> x11vnc (serves that screen) -> QMT + MCP supervisor
#
# Net effect: the container comes up healthy with no login at all, and a VNC
# client is only needed for the one-off interactive QMT account login.
#
# Run as wineuser (the entrypoint drops privileges via gosu/su).
set -uo pipefail

log() { echo "[start-vnc] $*" >&2; }

# Runtime + resolved-broker config bridged by the entrypoint.
if [ -f /opt/qmt-mcp/mcp.env ]; then
  set -a; . /opt/qmt-mcp/mcp.env; set +a
fi

VNC_DISPLAY_NUM="${QMT_VNC_DISPLAY:-20}"
DISPLAY_ADDR=":${VNC_DISPLAY_NUM}"
VNC_PORT="${QMT_VNC_PORT:-5900}"
GEOMETRY="${QMT_VNC_GEOMETRY:-1440x900x24}"
VNC_PASSWORD="${QMT_VNC_PASSWORD:-}"

export HOME="${HOME:-/home/wineuser}"
export DISPLAY="$DISPLAY_ADDR"
export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"

# Reap children and tear the stack down together: if any one of Xvfb / x11vnc /
# the supervisor dies, we exit so Docker's restart policy gets a clean slate
# rather than leaving a half-broken session listening.
pids=""
cleanup() {
  log "shutting down session"
  # shellcheck disable=SC2086
  [ -n "$pids" ] && kill $pids 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- 1) virtual screen -------------------------------------------------------
# -nolisten tcp: the X server itself is never exposed; only x11vnc reaches it.
log "starting Xvfb on ${DISPLAY_ADDR} (${GEOMETRY})"
Xvfb "$DISPLAY_ADDR" -screen 0 "$GEOMETRY" -nolisten tcp &
xvfb_pid=$!
pids="$xvfb_pid"

# Wait for the display to accept connections before anything binds to it.
# Probe the X socket directly rather than with xdpyinfo — x11-utils is not in the
# base image and this avoids pulling a package just for a readiness check.
X_SOCKET="/tmp/.X11-unix/X${VNC_DISPLAY_NUM}"
for _ in $(seq 1 30); do
  if [ -S "$X_SOCKET" ]; then break; fi
  if ! kill -0 "$xvfb_pid" 2>/dev/null; then
    log "FATAL: Xvfb exited during startup"; exit 30
  fi
  sleep 1
done
if [ ! -S "$X_SOCKET" ]; then
  log "FATAL: Xvfb did not become ready on ${DISPLAY_ADDR} (no socket at ${X_SOCKET})"; exit 30
fi
log "Xvfb ready"

# --- 2) VNC server -----------------------------------------------------------
# Password is mandatory: this screen is adjacent to a live brokerage terminal, so
# an open VNC port would be a trivial path to the trading session.
if [ -z "$VNC_PASSWORD" ]; then
  log "FATAL: QMT_VNC_PASSWORD is empty — refusing to serve an unauthenticated VNC desktop."
  exit 31
fi
VNC_PASSWD_FILE="$HOME/.vnc/passwd"
mkdir -p "$HOME/.vnc"
x11vnc -storepasswd "$VNC_PASSWORD" "$VNC_PASSWD_FILE" >/dev/null 2>&1
chmod 600 "$VNC_PASSWD_FILE"

log "starting x11vnc on :${VNC_PORT}"
x11vnc -display "$DISPLAY_ADDR" \
       -rfbport "$VNC_PORT" \
       -rfbauth "$VNC_PASSWD_FILE" \
       -forever -shared -noxdamage -repeat \
       -o "$HOME/.vnc/x11vnc.log" &
vnc_pid=$!
pids="$pids $vnc_pid"

# --- 3) desktop environment --------------------------------------------------
# Without a window manager the VNC client shows a bare black X root window: QMT's
# windows have no decorations, cannot be moved/resized, and dialogs can end up
# unreachable. The base image ships XFCE, so reuse it.
#
# We start xfwm4 + xfdesktop + xfce4-panel directly instead of
# `startxfce4`/`xfce4-session`: the full session manager wants D-Bus and a login
# session, which do not exist here, and it also owns the session lifecycle
# (logging out would kill the MCP). Warnings about a missing session manager /
# system bus are expected in the logs and harmless.
#
# XDG_RUNTIME_DIR keeps XFCE from complaining about a missing runtime dir.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-runtime-$(id -u)}"
mkdir -p "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"

if [ "${QMT_VNC_DESKTOP:-1}" = "1" ]; then
  log "starting window manager (xfwm4)"
  xfwm4 > "$HOME/.vnc/xfwm4.log" 2>&1 &
  wm_pid=$!
  pids="$pids $wm_pid"
  sleep 2

  # xfdesktop paints the wallpaper/root window, xfce4-panel is the taskbar.
  # Both are optional — the WM alone is enough to make QMT usable — so failures
  # here must not abort the session. Their D-Bus warnings (org.xfce.SessionManager
  # unknown, notification plugin) are expected and harmless without a session bus.
  log "starting desktop (xfdesktop)"
  xfdesktop > "$HOME/.vnc/xfdesktop.log" 2>&1 &
  pids="$pids $!"

  log "starting panel (xfce4-panel)"
  xfce4-panel > "$HOME/.vnc/xfce4-panel.log" 2>&1 &
  pids="$pids $!"
else
  log "desktop disabled (QMT_VNC_DESKTOP=0); serving a bare X root window"
  wm_pid=""
fi

# --- 4) QMT terminal ---------------------------------------------------------
# Backgrounded, not exec'd: the terminal is expected to be restarted by hand from
# a VNC session without taking the MCP down with it.
log "launching QMT terminal"
/usr/local/bin/start-qmt.sh > "$HOME/qmt-client.log" 2>&1 &
qmt_pid=$!
pids="$pids $qmt_pid"

# --- 5) MCP supervisor -------------------------------------------------------
# The supervisor restarts the MCP with capped backoff; it is the process whose
# death should bring the session down, so we wait on it below.
log "starting MCP supervisor"
/usr/local/bin/qmt-supervisor.sh &
sup_pid=$!
pids="$pids $sup_pid"

log "session up: Xvfb=${xvfb_pid} x11vnc=${vnc_pid} wm=${wm_pid:-off} qmt=${qmt_pid} supervisor=${sup_pid}"

# Exit as soon as the screen or the supervisor dies (QMT quitting is survivable,
# and so is the WM — losing decorations should not take the MCP down).
while true; do
  if ! kill -0 "$xvfb_pid" 2>/dev/null; then log "Xvfb died"; exit 32; fi
  if ! kill -0 "$vnc_pid"  2>/dev/null; then log "x11vnc died"; exit 33; fi
  if ! kill -0 "$sup_pid"  2>/dev/null; then log "MCP supervisor died"; exit 34; fi
  sleep 5
done
