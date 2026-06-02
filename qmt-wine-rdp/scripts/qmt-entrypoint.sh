#!/usr/bin/env bash
set -euo pipefail

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
    echo "QMT_CONNECT_RETRY='${QMT_CONNECT_RETRY:-8}'"
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
