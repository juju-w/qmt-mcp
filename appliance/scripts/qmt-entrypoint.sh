#!/usr/bin/env bash
set -euo pipefail

is_enabled() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    1 | yes | true | on) return 0 ;;
    *) return 1 ;;
  esac
}

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

VNC_ENABLED=0
if is_enabled "${QMT_VNC_ENABLED:-0}"; then
  VNC_ENABLED=1
fi
export QMT_VNC_ENABLED="$VNC_ENABLED"

if [ "$VNC_ENABLED" = "1" ] && [ "$DESKTOP_MODE" != "persistent" ]; then
  echo "[qmt-entrypoint] ERROR: VNC access requires QMT_DESKTOP_MODE=persistent" >&2
  exit 24
fi

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

if [ "$VNC_ENABLED" = "1" ]; then
  VNC_BIND_ADDRESS="${VNC_BIND_ADDRESS:-127.0.0.1}"
  case "$VNC_BIND_ADDRESS" in
    127.0.0.1 | ::1 | localhost) ;;
    *)
      if ! is_enabled "${QMT_VNC_ALLOW_LAN:-0}"; then
        echo "[qmt-entrypoint] ERROR: non-loopback VNC bind requires QMT_VNC_ALLOW_LAN=1" >&2
        exit 25
      fi
      ;;
  esac

  case "${QMT_VNC_CLIPBOARD:-none}" in
    none | text) ;;
    *)
      echo "[qmt-entrypoint] ERROR: QMT_VNC_CLIPBOARD must be none or text" >&2
      exit 26
      ;;
  esac
  case "${QMT_VNC_RESTART_BACKOFF_S:-2}" in
    '' | *[!0-9]*)
      echo "[qmt-entrypoint] ERROR: QMT_VNC_RESTART_BACKOFF_S must be an integer from 1 to 60" >&2
      exit 26
      ;;
  esac
  if [ "${QMT_VNC_RESTART_BACKOFF_S:-2}" -lt 1 ] || [ "${QMT_VNC_RESTART_BACKOFF_S:-2}" -gt 60 ]; then
    echo "[qmt-entrypoint] ERROR: QMT_VNC_RESTART_BACKOFF_S must be an integer from 1 to 60" >&2
    exit 26
  fi
fi

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

RUNTIME_UID="${USER_UID:-1000}"
RUNTIME_GID="${USER_GID:-1000}"

if [ "$VNC_ENABLED" = "1" ]; then
  VNC_PASSWORD=""
  if [ -n "${QMT_VNC_PASSWORD_FILE:-}" ]; then
    if [ ! -f "$QMT_VNC_PASSWORD_FILE" ] || [ -L "$QMT_VNC_PASSWORD_FILE" ] || [ ! -r "$QMT_VNC_PASSWORD_FILE" ]; then
      echo "[qmt-entrypoint] ERROR: QMT_VNC_PASSWORD_FILE must be a readable regular file" >&2
      exit 27
    fi
    vnc_secret_mode="$(stat -c '%a' "$QMT_VNC_PASSWORD_FILE")"
    if (( (8#$vnc_secret_mode & 077) != 0 )); then
      echo "[qmt-entrypoint] ERROR: QMT_VNC_PASSWORD_FILE must not grant group/other permissions" >&2
      exit 27
    fi
    IFS= read -r VNC_PASSWORD < "$QMT_VNC_PASSWORD_FILE" || [ -n "$VNC_PASSWORD" ]
  elif [ -n "${QMT_VNC_PASSWORD:-}" ]; then
    VNC_PASSWORD="$QMT_VNC_PASSWORD"
  else
    VNC_PASSWORD="$RDP_PASSWORD"
  fi

  if [ "${#VNC_PASSWORD}" -lt 8 ]; then
    echo "[qmt-entrypoint] ERROR: VNC password must be at least 8 characters" >&2
    exit 27
  fi
  VNC_PASSWORD_LOWER="$(printf '%s' "$VNC_PASSWORD" | tr '[:upper:]' '[:lower:]')"
  case "$VNC_PASSWORD_LOWER" in
    password* | changeme* | 12345678*)
      echo "[qmt-entrypoint] ERROR: effective VNC password matches a well-known default" >&2
      exit 27
      ;;
  esac

  install -d -m 0700 -o "$RUNTIME_UID" -g "$RUNTIME_GID" /run/qmt/vnc
  vnc_password_tmp="$(mktemp /run/qmt/vnc/passwd.XXXXXX)"
  if ! printf '%s\n' "$VNC_PASSWORD" | tigervncpasswd -f > "$vnc_password_tmp"; then
    rm -f "$vnc_password_tmp"
    echo "[qmt-entrypoint] ERROR: unable to create the VNC authentication file" >&2
    exit 27
  fi
  # The runtime intentionally lacks CAP_FOWNER, so set the mode before the
  # root-owned temporary file is handed to the desktop user.
  chmod 0600 "$vnc_password_tmp"
  chown "$RUNTIME_UID:$RUNTIME_GID" "$vnc_password_tmp"
  mv -f "$vnc_password_tmp" /run/qmt/vnc/passwd
  unset VNC_PASSWORD VNC_PASSWORD_LOWER QMT_VNC_PASSWORD
else
  # Remove only the auth artifact owned by this entrypoint. Do not recursively
  # touch the runtime directory in case an operator mounted something there.
  rm -f /run/qmt/vnc/passwd
  rmdir /run/qmt/vnc 2>/dev/null || true
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
