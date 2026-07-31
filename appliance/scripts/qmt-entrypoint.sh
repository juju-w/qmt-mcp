#!/usr/bin/env bash
set -euo pipefail

# Display mode (validated early so a typo fails before any service starts):
#   rdp  (default) — base-image xrdp only; QMT + MCP start from the XFCE autostart
#                    on RDP login. Unchanged legacy behaviour.
#   vnc            — headless Xvfb + x11vnc, with QMT + MCP owned by PID 1. The
#                    container self-heals to healthy with no login at all.
#   both           — xrdp in the background AND the headless VNC session.
QMT_DISPLAY_MODE="${QMT_DISPLAY_MODE:-rdp}"
case "$QMT_DISPLAY_MODE" in
  rdp | vnc | both) ;;
  *)
    echo "[qmt-entrypoint] FATAL: invalid QMT_DISPLAY_MODE='${QMT_DISPLAY_MODE}' (expected rdp|vnc|both)." >&2
    exit 21
    ;;
esac

# The VNC desktop is adjacent to a live brokerage terminal, so it is always
# password-protected. Fall back to the RDP password so a `vnc` deployment needs
# one fewer secret; fail closed if neither is set.
if [ "$QMT_DISPLAY_MODE" != "rdp" ]; then
  QMT_VNC_PASSWORD="${QMT_VNC_PASSWORD:-${QMT_RDP_PASSWORD:-}}"
  if [ -z "$QMT_VNC_PASSWORD" ]; then
    echo "[qmt-entrypoint] FATAL: QMT_DISPLAY_MODE=${QMT_DISPLAY_MODE} needs QMT_VNC_PASSWORD (or QMT_RDP_PASSWORD) set." >&2
    exit 22
  fi
  export QMT_VNC_PASSWORD
fi

# 0) Storage guard (005): the broker pack / userdata should live on real disk; a
#    RAM-backed mount (tmpfs/ramfs) can exhaust memory. Warn by default; set
#    QMT_ENFORCE_REALDISK=1 to fail closed.
BROKER_MOUNT="${BROKER_MOUNT:-/broker}"
if fstype="$(stat -f -c %T "$BROKER_MOUNT" 2>/dev/null)"; then
  case "$fstype" in
    tmpfs | ramfs)
      msg="[qmt-entrypoint] WARNING: ${BROKER_MOUNT} is on ${fstype} (RAM-backed); the broker pack/userdata should be on real disk."
      if [ "${QMT_ENFORCE_REALDISK:-0}" = "1" ]; then
        echo "${msg} refusing to start (QMT_ENFORCE_REALDISK=1)." >&2
        exit 20
      fi
      echo "${msg} set QMT_ENFORCE_REALDISK=1 to enforce." >&2
      ;;
  esac
fi

# 1) Resolve the mounted broker pack (fail fast before starting any service).
#    Writes /run/qmt/broker.env (Wine paths, no secrets).
/usr/local/bin/detect-broker.py
# shellcheck disable=SC1091
. /run/qmt/broker.env

# 2) RDP password. We pre-create wineuser at BUILD time (for Wine provisioning),
#    so the base entrypoint finds the user already present and SKIPS useradd —
#    meaning it never applies USER_PASSWD. Set the password directly each start.
if [ -z "${USER_PASSWD:-}" ] && [ -n "${QMT_RDP_PASSWORD:-}" ]; then
  USER_PASSWD="$(openssl passwd -1 -salt qmt "${QMT_RDP_PASSWORD}")"
  export USER_PASSWD
fi
if [ -n "${QMT_RDP_PASSWORD:-}" ]; then
  echo "${USER_NAME:-wineuser}:${QMT_RDP_PASSWORD}" | chpasswd
fi

# 3) Bridge runtime + resolved config to the RDP/XFCE session (which does not
#    reliably inherit container env). start-mcp.sh / start-qmt.sh source this.
if [ -d /opt/qmt-mcp ]; then
  # Single-quote every value: Wine paths contain backslashes that bash `source`
  # in start-mcp.sh / start-qmt.sh would otherwise strip.
  {
    echo "QMT_MCP_AUTH_MODE='${QMT_MCP_AUTH_MODE:-static}'"
    echo "QMT_MCP_TOKEN='${QMT_MCP_TOKEN:-}'"
    echo "MCP_HOST='${MCP_HOST:-0.0.0.0}'"
    echo "MCP_PORT='${MCP_PORT:-8765}'"
    echo "QMT_MCP_TRANSPORT='${QMT_MCP_TRANSPORT:-streamable-http}'"
    echo "QMT_MCP_PUBLIC_BASE_URL='${QMT_MCP_PUBLIC_BASE_URL:-}'"
    echo "QMT_MCP_OAUTH_AUTHORIZATION_SERVERS='${QMT_MCP_OAUTH_AUTHORIZATION_SERVERS:-}'"
    echo "QMT_MCP_OAUTH_ISSUER='${QMT_MCP_OAUTH_ISSUER:-}'"
    echo "QMT_MCP_OAUTH_JWKS_URL='${QMT_MCP_OAUTH_JWKS_URL:-}'"
    echo "QMT_MCP_OAUTH_SCOPES='${QMT_MCP_OAUTH_SCOPES:-qmt:read qmt:market qmt:account qmt:manage qmt:admin}'"
    echo "QMT_MCP_OAUTH_RESOURCE='${QMT_MCP_OAUTH_RESOURCE:-}'"
    echo "QMT_MCP_OAUTH_RESOURCE_NAME='${QMT_MCP_OAUTH_RESOURCE_NAME:-QMT MCP}'"
    echo "QMT_MCP_OAUTH_ALGORITHMS='${QMT_MCP_OAUTH_ALGORITHMS:-RS256 ES256}'"
    echo "QMT_MCP_OAUTH_CLOCK_SKEW_S='${QMT_MCP_OAUTH_CLOCK_SKEW_S:-30}'"
    echo "QMT_MCP_OAUTH_JWKS_TTL_S='${QMT_MCP_OAUTH_JWKS_TTL_S:-300}'"
    echo "QMT_MCP_OAUTH_HTTP_TIMEOUT_S='${QMT_MCP_OAUTH_HTTP_TIMEOUT_S:-5}'"
    echo "QMT_MCP_OAUTH_JWKS_MAX_BYTES='${QMT_MCP_OAUTH_JWKS_MAX_BYTES:-1048576}'"
    echo "QMT_CONNECT_RETRY='${QMT_CONNECT_RETRY:-8}'"
    echo "QMT_READINESS_POLL_S='${QMT_READINESS_POLL_S:-5}'"
    echo "QMT_ENABLE_CONNECTOR='${QMT_ENABLE_CONNECTOR:-0}'"
    echo "QMT_CONNECT_BACKOFF_MAX_S='${QMT_CONNECT_BACKOFF_MAX_S:-60}'"
    echo "QMT_ENABLE_XTTRADE_QUERY='${QMT_ENABLE_XTTRADE_QUERY:-0}'"
    echo "QMT_TRADE_ACCOUNTS='${QMT_TRADE_ACCOUNTS:-}'"
    echo "QMT_TRADE_ACCOUNT_TYPE='${QMT_TRADE_ACCOUNT_TYPE:-STOCK}'"
    echo "QMT_DB_URL='${QMT_DB_URL:-}'"
    echo "QMT_DB_MARKETDATA='${QMT_DB_MARKETDATA:-1}'"
    echo "QMT_DB_POOL_MAX='${QMT_DB_POOL_MAX:-5}'"
    echo "QMT_QUOTE_SUBSCRIPTION_STORE='${QMT_QUOTE_SUBSCRIPTION_STORE:-/broker/cache/quote-subscriptions-v1.json}'"
    echo "QMT_QUOTE_CACHE_MAX_AGE_MS='${QMT_QUOTE_CACHE_MAX_AGE_MS:-10000}'"
    echo "QMT_QUOTE_SUBSCRIPTION_MAX_CODES='${QMT_QUOTE_SUBSCRIPTION_MAX_CODES:-100}'"
    echo "QMT_QUOTE_SUBSCRIPTION_MAX_OFFICIAL='${QMT_QUOTE_SUBSCRIPTION_MAX_OFFICIAL:-50}'"
    echo "QMT_QUOTE_SUBSCRIPTION_MIN_FALLBACK_INTERVAL_S='${QMT_QUOTE_SUBSCRIPTION_MIN_FALLBACK_INTERVAL_S:-5}'"
    echo "QMT_ENABLE_XTDATA_SECTOR_WRITE='${QMT_ENABLE_XTDATA_SECTOR_WRITE:-0}'"
    echo "QMT_XTDATA_SECTOR_WRITE_PREFIXES='${QMT_XTDATA_SECTOR_WRITE_PREFIXES:-MCP/,AI/}'"
    echo "QMT_ENABLE_FORMULA_RUNTIME='${QMT_ENABLE_FORMULA_RUNTIME:-0}'"
    echo "QMT_FORMULA_ALLOWLIST='${QMT_FORMULA_ALLOWLIST:-}'"
    echo "QMT_FORMULA_OUTPUT_SANDBOX='${QMT_FORMULA_OUTPUT_SANDBOX:-/broker/formula-output}'"
    echo "QMT_BROKER_ID='${QMT_BROKER_ID:-}'"
    echo "QMT_CLIENT='${QMT_CLIENT:-}'"
    echo "QMT_CLIENT_WIN='${QMT_CLIENT_WIN:-}'"
    echo "QMT_BIN_DIR_WIN='${QMT_BIN_DIR_WIN:-}'"
    echo "QMT_BIN_DIR='${QMT_BIN_DIR:-}'"
    echo "QMT_USERDATA_WIN='${QMT_USERDATA_WIN:-}'"
    echo "QMT_XTQUANT_DIR_WIN='${QMT_XTQUANT_DIR_WIN:-}'"
    echo "QMT_MCP_MODE='${QMT_MCP_MODE:-readonly}'"
    echo "QMT_DISPLAY_MODE='${QMT_DISPLAY_MODE}'"
    echo "QMT_VNC_DISPLAY='${QMT_VNC_DISPLAY:-20}'"
    echo "QMT_VNC_PORT='${QMT_VNC_PORT:-5900}'"
    echo "QMT_VNC_GEOMETRY='${QMT_VNC_GEOMETRY:-1440x900x24}'"
    echo "QMT_VNC_PASSWORD='${QMT_VNC_PASSWORD:-}'"
    echo "QMT_VNC_DESKTOP='${QMT_VNC_DESKTOP:-1}'"
  } > /opt/qmt-mcp/mcp.env
  chown "${USER_UID:-1000}:${USER_GID:-1000}" /opt/qmt-mcp/mcp.env 2>/dev/null || true
  chmod 600 /opt/qmt-mcp/mcp.env 2>/dev/null || true
fi

# 4) Hand off to the display stack.
#
# rdp: unchanged — the base entrypoint runs xrdp in the foreground as PID 1 and
# the XFCE autostart brings up QMT + MCP once an operator logs in.
if [ "$QMT_DISPLAY_MODE" = "rdp" ]; then
  exec /usr/bin/entrypoint "$@"
fi

# vnc / both: run the headless session as wineuser. The XFCE autostart never
# fires here (nobody logs into a desktop), so start-vnc.sh owns Xvfb + x11vnc +
# QMT + the MCP supervisor directly — that is what makes the MCP available
# without any interactive login.
#
# `both` additionally starts xrdp in the background so an operator can still get
# in over RDP; note that an RDP login lands in a SEPARATE X session from the VNC
# screen, and its autostart would spawn a second QMT/MCP. qmt-supervisor.sh has a
# pidfile guard so the MCP stays single-instance; the QMT terminal does not, so
# prefer `vnc` unless you specifically need the RDP path.
if [ "$QMT_DISPLAY_MODE" = "both" ]; then
  if [ -f /usr/sbin/xrdp ]; then
    rm -f /var/run/xrdp/xrdp-sesman.pid /var/run/xrdp/xrdp.pid
    /usr/sbin/xrdp-sesman
    /usr/sbin/xrdp
    echo "[qmt-entrypoint] xrdp started in background (mode=both)" >&2
  else
    echo "[qmt-entrypoint] WARNING: xrdp absent in this image; continuing with VNC only." >&2
  fi
fi

echo "[qmt-entrypoint] display mode=${QMT_DISPLAY_MODE}; handing off to start-vnc.sh as ${USER_NAME:-wineuser}" >&2
exec gosu "${USER_NAME:-wineuser}" /usr/local/bin/start-vnc.sh
