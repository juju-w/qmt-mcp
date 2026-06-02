#!/usr/bin/env bash
set -euo pipefail

if [ -z "${USER_PASSWD:-}" ] && [ -n "${QMT_RDP_PASSWORD:-}" ]; then
  USER_PASSWD="$(openssl passwd -1 -salt qmt "${QMT_RDP_PASSWORD}")"
  export USER_PASSWD
fi

# Bridge runtime env (token/host/port/mini-path) to the RDP/XFCE session, which
# does not reliably inherit the container environment. start-mcp.sh sources this.
if [ -d /opt/qmt-mcp ]; then
  {
    echo "QMT_MCP_TOKEN=${QMT_MCP_TOKEN:-}"
    echo "MCP_HOST=${MCP_HOST:-0.0.0.0}"
    echo "MCP_PORT=${MCP_PORT:-8765}"
    echo "QMT_MINI_PATH=${QMT_MINI_PATH:-Z:\\workspace\\QMT\\extracted\\userdata_mini}"
    echo "QMT_CONNECT_RETRY=${QMT_CONNECT_RETRY:-8}"
  } > /opt/qmt-mcp/mcp.env
  chown "${USER_UID:-1000}:${USER_GID:-1000}" /opt/qmt-mcp/mcp.env 2>/dev/null || true
  chmod 600 /opt/qmt-mcp/mcp.env 2>/dev/null || true
fi

exec /usr/bin/entrypoint "$@"
