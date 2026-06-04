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
    echo "QMT_MCP_TOKEN='${QMT_MCP_TOKEN:-}'"
    echo "MCP_HOST='${MCP_HOST:-0.0.0.0}'"
    echo "MCP_PORT='${MCP_PORT:-8765}'"
    echo "QMT_MCP_TRANSPORT='${QMT_MCP_TRANSPORT:-streamable-http}'"
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
  } > /opt/qmt-mcp/mcp.env
  chown "${USER_UID:-1000}:${USER_GID:-1000}" /opt/qmt-mcp/mcp.env 2>/dev/null || true
  chmod 600 /opt/qmt-mcp/mcp.env 2>/dev/null || true
fi

exec /usr/bin/entrypoint "$@"
