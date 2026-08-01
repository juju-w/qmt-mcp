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
  set -a
  # Operator-selected env file is intentional.
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

fail=0
warn=0
err()  { printf '  [FAIL] %s\n' "$1"; fail=$((fail + 1)); }
note() { printf '  [WARN] %s\n' "$1"; warn=$((warn + 1)); }
ok()   { printf '  [ok]   %s\n' "$1"; }
is_enabled() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    1 | yes | true | on) return 0 ;;
    *) return 1 ;;
  esac
}

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

# 2) Persistent desktop and RDP credential policy (026).
DESKTOP_MODE="${QMT_DESKTOP_MODE:-manual}"
case "$DESKTOP_MODE" in
  manual | persistent) ok "Desktop mode is ${DESKTOP_MODE}." ;;
  *) err "QMT_DESKTOP_MODE must be manual or persistent." ;;
esac

RDP_PW=""
if [ -n "${QMT_RDP_PASSWORD_FILE:-}" ]; then
  if [ ! -f "$QMT_RDP_PASSWORD_FILE" ] || [ -L "$QMT_RDP_PASSWORD_FILE" ] || [ ! -r "$QMT_RDP_PASSWORD_FILE" ]; then
    err "QMT_RDP_PASSWORD_FILE must be a readable regular file."
  else
    if secret_mode="$(stat -c '%a' "$QMT_RDP_PASSWORD_FILE" 2>/dev/null)"; then
      :
    else
      secret_mode="$(stat -f '%Lp' "$QMT_RDP_PASSWORD_FILE")"
    fi
    if (( (8#$secret_mode & 077) != 0 )); then
      err "QMT_RDP_PASSWORD_FILE must not grant group/other permissions."
    fi
    IFS= read -r RDP_PW < "$QMT_RDP_PASSWORD_FILE" || [ -n "$RDP_PW" ]
    ok "RDP password is file-backed."
  fi
else
  RDP_PW="${QMT_RDP_PASSWORD:-}"
  note "RDP password uses an environment variable; a mounted secret file is safer."
fi
if [ -z "$RDP_PW" ] || [ "$RDP_PW" = "qmt" ] || [ "$RDP_PW" = "changeme" ] || [ "$RDP_PW" = "password" ]; then
  err "RDP password is empty or a well-known default — set a unique password."
elif [ "${#RDP_PW}" -lt 12 ]; then
  err "RDP password is too short (${#RDP_PW} chars); use >= 12 chars."
else
  ok "RDP password is set, non-default, and >= 12 chars."
fi

RDP_BIND="${RDP_BIND_ADDRESS:-127.0.0.1}"
case "$RDP_BIND" in
  127.0.0.1 | ::1 | localhost) ok "RDP publication is loopback-only." ;;
  *)
    case "${QMT_RDP_ALLOW_LAN:-0}" in
      1 | yes | true | on) note "RDP is intentionally published to ${RDP_BIND}; keep it on a trusted LAN/VPN." ;;
      *) err "Non-loopback RDP publication requires QMT_RDP_ALLOW_LAN=1." ;;
    esac
    ;;
esac

if is_enabled "${QMT_RDP_DRIVE_REDIRECTION:-0}"; then
  if is_enabled "${QMT_RDP_ALLOW_UNSAFE_CHANNELS:-0}"; then
    note "RDP drive redirection is explicitly enabled."
  else
    err "RDP drive redirection requires QMT_RDP_ALLOW_UNSAFE_CHANNELS=1."
  fi
else
  ok "RDP drive redirection is disabled."
fi

case "${QMT_RDP_CERT_MODE:-generated}" in
  generated | self-signed) ok "RDP uses a persisted per-instance certificate." ;;
  mounted | provided)
    [ -r "${QMT_RDP_CERT_FILE:-}" ] || err "QMT_RDP_CERT_FILE is required and must be readable."
    [ -r "${QMT_RDP_KEY_FILE:-}" ] || err "QMT_RDP_KEY_FILE is required and must be readable."
    ;;
  *) err "QMT_RDP_CERT_MODE must be generated or mounted." ;;
esac

# 3) Optional VNC client access (027). Raw VNC is an authenticated adapter to
# the persistent desktop, not a second X/QMT session.
if is_enabled "${QMT_VNC_ENABLED:-0}"; then
  if [ "$DESKTOP_MODE" != "persistent" ]; then
    err "VNC access requires QMT_DESKTOP_MODE=persistent."
  else
    ok "VNC attaches to persistent desktop mode."
  fi

  VNC_PW=""
  if [ -n "${QMT_VNC_PASSWORD_FILE:-}" ]; then
    if [ ! -f "$QMT_VNC_PASSWORD_FILE" ] || [ -L "$QMT_VNC_PASSWORD_FILE" ] || [ ! -r "$QMT_VNC_PASSWORD_FILE" ]; then
      err "QMT_VNC_PASSWORD_FILE must be a readable regular file."
    else
      if vnc_secret_mode="$(stat -c '%a' "$QMT_VNC_PASSWORD_FILE" 2>/dev/null)"; then
        :
      else
        vnc_secret_mode="$(stat -f '%Lp' "$QMT_VNC_PASSWORD_FILE")"
      fi
      if (( (8#$vnc_secret_mode & 077) != 0 )); then
        err "QMT_VNC_PASSWORD_FILE must not grant group/other permissions."
      fi
      IFS= read -r VNC_PW < "$QMT_VNC_PASSWORD_FILE" || [ -n "$VNC_PW" ]
      ok "VNC password is file-backed."
    fi
  elif [ -n "${QMT_VNC_PASSWORD:-}" ]; then
    VNC_PW="$QMT_VNC_PASSWORD"
    note "VNC password uses an environment variable; a mounted secret file is safer."
  else
    VNC_PW="$RDP_PW"
    note "VNC falls back to the RDP password; a unique file-backed VNC secret is safer."
  fi

  if [ "${#VNC_PW}" -lt 8 ]; then
    err "VNC password is too short (${#VNC_PW} chars); use >= 8 chars."
  else
    VNC_PW_LOWER="$(printf '%s' "$VNC_PW" | tr '[:upper:]' '[:lower:]')"
    case "$VNC_PW_LOWER" in
      password* | changeme* | 12345678*)
        err "Effective VNC password matches a well-known 8-character default."
        ;;
      *) ok "VNC password is set, non-default, and >= 8 chars." ;;
    esac
  fi

  VNC_BIND="${VNC_BIND_ADDRESS:-127.0.0.1}"
  case "$VNC_BIND" in
    127.0.0.1 | ::1 | localhost) ok "VNC publication is loopback-only." ;;
    *)
      if is_enabled "${QMT_VNC_ALLOW_LAN:-0}"; then
        note "VNC is intentionally published to ${VNC_BIND}; keep it on a trusted LAN/VPN."
      else
        err "Non-loopback VNC publication requires QMT_VNC_ALLOW_LAN=1."
      fi
      ;;
  esac

  case "${QMT_VNC_CLIPBOARD:-none}" in
    none) ok "VNC clipboard exchange is disabled." ;;
    text) note "VNC text clipboard exchange is explicitly enabled." ;;
    *) err "QMT_VNC_CLIPBOARD must be none or text." ;;
  esac
  note "Raw VNC is not transport-encrypted and uses only the first 8 password characters; use SSH/VPN."
else
  ok "VNC access is disabled."
fi

# 4) Network exposure: 0.0.0.0 bind is only safe behind a TLS reverse proxy.
HOST="${MCP_HOST:-0.0.0.0}"
PROXIED="${QMT_BEHIND_TLS_PROXY:-0}"
if [ "$HOST" = "0.0.0.0" ] && [ "$PROXIED" != "1" ]; then
  note "MCP binds 0.0.0.0 without QMT_BEHIND_TLS_PROXY=1 — expose only via a TLS"
  note "reverse proxy (see docs/DEPLOY.md), bind 127.0.0.1, or use a tunnel/VPN."
else
  ok "MCP exposure looks intentional (loopback or declared TLS proxy)."
fi

# 5) TLS reminder for non-proxied public bind.
if [ "$PROXIED" != "1" ]; then
  note "No TLS proxy declared — bearer credentials over plain HTTP are sniffable on a LAN."
fi

# 6) Remote desktop should not be on the public internet.
note "RDP is TLS-only but must still stay off the public internet (tunnel/VPN/loopback)."

echo "harden-check: ${fail} failure(s), ${warn} warning(s)."
[ "$fail" -eq 0 ] || { echo "harden-check: FAILED — fix the [FAIL] items before exposing."; exit 1; }
echo "harden-check: PASSED (review warnings)."
