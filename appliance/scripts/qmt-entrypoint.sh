#!/usr/bin/env bash
set -euo pipefail

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

# 2) Secure RDP setup (026). Password files are preferred so the credential is
#    absent from Docker metadata. Environment input remains for compatibility.
DESKTOP_MODE="${QMT_DESKTOP_MODE:-manual}"
case "$DESKTOP_MODE" in
  manual | persistent) ;;
  *) echo "[qmt-entrypoint] ERROR: QMT_DESKTOP_MODE must be manual or persistent" >&2; exit 21 ;;
esac

RDP_BIND_ADDRESS="${RDP_BIND_ADDRESS:-127.0.0.1}"
case "$RDP_BIND_ADDRESS" in
  127.0.0.1 | ::1 | localhost) ;;
  *)
    case "${QMT_RDP_ALLOW_LAN:-0}" in
      1 | yes | true | on) ;;
      *)
        echo "[qmt-entrypoint] ERROR: non-loopback RDP bind requires QMT_RDP_ALLOW_LAN=1" >&2
        exit 22
        ;;
    esac
    ;;
esac

RDP_PASSWORD=""
if [ -n "${QMT_RDP_PASSWORD_FILE:-}" ]; then
  if [ ! -f "$QMT_RDP_PASSWORD_FILE" ] || [ -L "$QMT_RDP_PASSWORD_FILE" ] || [ ! -r "$QMT_RDP_PASSWORD_FILE" ]; then
    echo "[qmt-entrypoint] ERROR: QMT_RDP_PASSWORD_FILE must be a readable regular file" >&2
    exit 23
  fi
  secret_mode="$(stat -c '%a' "$QMT_RDP_PASSWORD_FILE")"
  if (( (8#$secret_mode & 077) != 0 )); then
    echo "[qmt-entrypoint] ERROR: QMT_RDP_PASSWORD_FILE must not grant group/other permissions" >&2
    exit 23
  fi
  IFS= read -r RDP_PASSWORD < "$QMT_RDP_PASSWORD_FILE" || [ -n "$RDP_PASSWORD" ]
else
  RDP_PASSWORD="${QMT_RDP_PASSWORD:-}"
fi

case "$RDP_PASSWORD" in
  '' | qmt | changeme | password)
    echo "[qmt-entrypoint] ERROR: set a unique RDP password (file-backed preferred)" >&2
    exit 23
    ;;
esac
if [ "${#RDP_PASSWORD}" -lt 12 ]; then
  echo "[qmt-entrypoint] ERROR: RDP password must be at least 12 characters" >&2
  exit 23
fi

printf '%s:%s\n' "${USER_NAME:-wineuser}" "$RDP_PASSWORD" | chpasswd
unset RDP_PASSWORD

# Never grant the desktop account sudo in this appliance. The inherited base
# entrypoint enforces this flag before starting xrdp.
export USER_SUDO=no
/usr/local/bin/configure-xrdp.sh

# Containers do not run pam_systemd, so the per-user runtime directory is not
# created automatically. XFCE autostart uses it for flock-backed QMT/MCP
# singletons; create it before the session starts with the same ownership and
# permissions systemd-logind would use.
RUNTIME_UID="${USER_UID:-1000}"
RUNTIME_GID="${USER_GID:-1000}"
install -d -m 0700 -o "$RUNTIME_UID" -g "$RUNTIME_GID" "/run/user/${RUNTIME_UID}"
install -d -m 1777 /tmp/.ICE-unix

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
    echo "QMT_DESKTOP_MODE='${DESKTOP_MODE}'"
  } > /opt/qmt-mcp/mcp.env
  chown "${USER_UID:-1000}:${USER_GID:-1000}" /opt/qmt-mcp/mcp.env 2>/dev/null || true
  chmod 600 /opt/qmt-mcp/mcp.env 2>/dev/null || true
fi

if [ "$DESKTOP_MODE" = "persistent" ]; then
  # The base entrypoint starts xrdp and sesman first. Keep the desktop
  # supervisor as PID 1 so container health follows the long-lived session.
  export RUN_AS_ROOT=yes
  exec /usr/bin/entrypoint /usr/local/bin/persistent-desktop-supervisor.sh
fi

exec /usr/bin/entrypoint "$@"
