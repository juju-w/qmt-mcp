#!/usr/bin/env bash
# Pre-flight security check before exposing the QMT-MCP appliance beyond loopback.
# Flags weak/default config. Hard failures -> non-zero exit (gate a deploy with it).
# Never prints secret values. Reads an env file (arg 1, default ./appliance/.env)
# if present, falling back to the current environment.
#
# Usage:
#   scripts/harden-check.sh [path/to/.env]
#   QMT_MCP_TOKEN=... QMT_RDP_PASSWORD=... scripts/harden-check.sh
set -euo pipefail

ENV_FILE="${1:-appliance/.env}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a; . "$ENV_FILE"; set +a
fi

fail=0
warn=0
err()  { printf '  [FAIL] %s\n' "$1"; fail=$((fail + 1)); }
note() { printf '  [WARN] %s\n' "$1"; warn=$((warn + 1)); }
ok()   { printf '  [ok]   %s\n' "$1"; }

echo "harden-check: QMT-MCP appliance pre-flight"
echo "(env source: ${ENV_FILE}$([ -f "$ENV_FILE" ] || echo ' [not found, using process env]'))"

# 1) Authentication mode. The application repeats these checks at startup.
AUTH_MODE="$(printf '%s' "${QMT_MCP_AUTH_MODE:-static}" | tr '[:upper:]' '[:lower:]')"
case "$AUTH_MODE" in
  static | oauth | hybrid) ok "Authentication mode is ${AUTH_MODE}." ;;
  *) err "QMT_MCP_AUTH_MODE must be static, oauth, or hybrid." ;;
esac

# Static bearer strength (length only; never echo the value).
if [ "$AUTH_MODE" = "static" ] || [ "$AUTH_MODE" = "hybrid" ]; then
  TOKEN="${QMT_MCP_TOKEN:-}"
  if [ -z "$TOKEN" ]; then
    err "QMT_MCP_TOKEN is required in ${AUTH_MODE} mode."
  elif [ "$TOKEN" = "changeme" ] || [ "$TOKEN" = "qmt" ] || [ "$TOKEN" = "token" ]; then
    err "QMT_MCP_TOKEN is a well-known default — set a unique random token."
  elif [ "${#TOKEN}" -lt 32 ]; then
    err "QMT_MCP_TOKEN is too short (${#TOKEN} chars); use >= 32 random chars."
  else
    ok "QMT_MCP_TOKEN present and >= 32 chars."
  fi
fi

secure_url() {
  case "$1" in
    https://*) return 0 ;;
    http://localhost/* | http://localhost:* | http://127.0.0.1/* | http://127.0.0.1:*) return 0 ;;
    *) return 1 ;;
  esac
}

if [ "$AUTH_MODE" = "oauth" ] || [ "$AUTH_MODE" = "hybrid" ]; then
  ISSUER="${QMT_MCP_OAUTH_ISSUER:-}"
  SERVERS="${QMT_MCP_OAUTH_AUTHORIZATION_SERVERS:-$ISSUER}"
  JWKS="${QMT_MCP_OAUTH_JWKS_URL:-}"
  RESOURCE="${QMT_MCP_OAUTH_RESOURCE:-}"
  if [ -z "$RESOURCE" ] && [ -n "${QMT_MCP_PUBLIC_BASE_URL:-}" ]; then
    RESOURCE="${QMT_MCP_PUBLIC_BASE_URL%/}/mcp"
  fi
  for pair in "issuer:$ISSUER" "JWKS URL:$JWKS" "resource:$RESOURCE"; do
    label="${pair%%:*}"
    value="${pair#*:}"
    if [ -z "$value" ]; then
      err "OAuth ${label} is required in ${AUTH_MODE} mode."
    elif ! secure_url "$value"; then
      err "OAuth ${label} must use HTTPS (loopback HTTP is development-only)."
    fi
  done
  if [ -z "$SERVERS" ] || [ "$SERVERS" != "$ISSUER" ]; then
    err "QMT_MCP_OAUTH_AUTHORIZATION_SERVERS must contain exactly the configured issuer."
  else
    ok "OAuth issuer, JWKS, resource, and authorization server are pinned."
  fi
fi

# 2) RDP password (default in compose is 'qmt').
RDP_PW="${QMT_RDP_PASSWORD:-}"
if [ -z "$RDP_PW" ] || [ "$RDP_PW" = "qmt" ]; then
  err "QMT_RDP_PASSWORD is empty or the default 'qmt' — set a strong password."
elif [ "${#RDP_PW}" -lt 12 ]; then
  note "QMT_RDP_PASSWORD is short (< 12 chars)."
else
  ok "QMT_RDP_PASSWORD set and non-default."
fi

# 3) Network exposure: 0.0.0.0 bind is only safe behind a TLS reverse proxy.
HOST="${MCP_HOST:-0.0.0.0}"
PROXIED="${QMT_BEHIND_TLS_PROXY:-0}"
if [ "$HOST" = "0.0.0.0" ] && [ "$PROXIED" != "1" ]; then
  note "MCP binds 0.0.0.0 without QMT_BEHIND_TLS_PROXY=1 — expose only via a TLS"
  note "reverse proxy (see docs/DEPLOY.md), bind 127.0.0.1, or use a tunnel/VPN."
else
  ok "MCP exposure looks intentional (loopback or declared TLS proxy)."
fi

# 4) TLS reminder for non-proxied public bind.
if [ "$PROXIED" != "1" ]; then
  note "No TLS proxy declared — bearer credentials over plain HTTP are sniffable on a LAN."
fi

# 5) RDP should not be on the public internet.
note "Ensure the RDP port is NOT published to the public internet (tunnel/VPN/loopback)."

echo "harden-check: ${fail} failure(s), ${warn} warning(s)."
[ "$fail" -eq 0 ] || { echo "harden-check: FAILED — fix the [FAIL] items before exposing."; exit 1; }
echo "harden-check: PASSED (review warnings)."
