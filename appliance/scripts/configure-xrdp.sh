#!/usr/bin/env bash
# Apply the appliance's xrdp policy and provision its per-instance TLS identity.
set -euo pipefail

XRDP_INI="${XRDP_INI:-/etc/xrdp/xrdp.ini}"
SESMAN_INI="${SESMAN_INI:-/etc/xrdp/sesman.ini}"
CERT_DIR="${QMT_RDP_CERT_DIR:-/var/lib/qmt-rdp}"
CERT_FILE="${CERT_DIR}/cert.pem"
KEY_FILE="${CERT_DIR}/key.pem"
USER_NAME="${USER_NAME:-wineuser}"

log() { printf '[configure-xrdp] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

is_enabled() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    1 | yes | true | on) return 0 ;;
    *) return 1 ;;
  esac
}

set_ini_value() {
  local file="$1" section="$2" key="$3" value="$4" tmp
  tmp="$(mktemp)"
  awk -v wanted_section="$section" -v wanted_key="$key" -v wanted_value="$value" '
    /^\[[^]]+\][[:space:]]*$/ {
      current = $0
      sub(/^\[/, "", current)
      sub(/\][[:space:]]*$/, "", current)
    }
    current == wanted_section {
      line = $0
      sub(/^[#;][[:space:]]*/, "", line)
      split(line, pair, "=")
      candidate = pair[1]
      gsub(/[[:space:]]/, "", candidate)
      if (candidate == wanted_key) {
        print wanted_key "=" wanted_value
        found = 1
        next
      }
    }
    { print }
    END { if (!found) exit 42 }
  ' "$file" > "$tmp" || {
    local code=$?
    rm -f "$tmp"
    die "cannot set [${section}] ${key} in ${file} (awk=${code})"
  }
  cat "$tmp" > "$file"
  rm -f "$tmp"
}

install_cert_pair() {
  local source_cert="$1" source_key="$2"
  install -m 0640 -o root -g xrdp "$source_cert" "$CERT_FILE"
  install -m 0640 -o root -g xrdp "$source_key" "$KEY_FILE"
}

cert_pair_matches() {
  local cert_hash key_hash
  cert_hash="$(openssl x509 -in "$CERT_FILE" -pubkey -noout 2>/dev/null | sha256sum | cut -d' ' -f1)" || return 1
  key_hash="$(openssl pkey -in "$KEY_FILE" -pubout 2>/dev/null | sha256sum | cut -d' ' -f1)" || return 1
  [ -n "$cert_hash" ] && [ "$cert_hash" = "$key_hash" ]
}

provision_certificate() {
  local mode="${QMT_RDP_CERT_MODE:-generated}" instance cn tmp_cert tmp_key
  install -d -m 0750 -o root -g xrdp "$CERT_DIR"

  case "$mode" in
    generated | self-signed)
      if [ -s "$CERT_FILE" ] && [ -s "$KEY_FILE" ] \
          && cert_pair_matches \
          && openssl x509 -checkend 2592000 -noout -in "$CERT_FILE" >/dev/null 2>&1; then
        log "using persisted per-instance TLS certificate"
        return
      fi
      instance="${INSTANCE:-default}"
      cn="qmt-$(printf '%s' "$instance" | tr -cd 'A-Za-z0-9_.-')"
      [ "$cn" != "qmt-" ] || cn="qmt-instance"
      tmp_cert="${CERT_FILE}.new"
      tmp_key="${KEY_FILE}.new"
      openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 825 \
        -subj "/CN=${cn}" -keyout "$tmp_key" -out "$tmp_cert" >/dev/null 2>&1
      install_cert_pair "$tmp_cert" "$tmp_key"
      rm -f "$tmp_cert" "$tmp_key"
      log "generated per-instance TLS certificate (CN=${cn})"
      ;;
    mounted | provided)
      : "${QMT_RDP_CERT_FILE:?QMT_RDP_CERT_FILE is required when QMT_RDP_CERT_MODE=mounted}"
      : "${QMT_RDP_KEY_FILE:?QMT_RDP_KEY_FILE is required when QMT_RDP_CERT_MODE=mounted}"
      [ -r "$QMT_RDP_CERT_FILE" ] || die "provided certificate is not readable"
      [ -r "$QMT_RDP_KEY_FILE" ] || die "provided private key is not readable"
      install_cert_pair "$QMT_RDP_CERT_FILE" "$QMT_RDP_KEY_FILE"
      cert_pair_matches || die "provided certificate and private key do not match"
      log "installed provided TLS certificate"
      ;;
    *) die "QMT_RDP_CERT_MODE must be generated or mounted" ;;
  esac
}

configure_channels() {
  local clipboard="${QMT_RDP_CLIPBOARD:-none}" drive="${QMT_RDP_DRIVE_REDIRECTION:-0}"
  local unsafe="${QMT_RDP_ALLOW_UNSAFE_CHANNELS:-0}"

  if is_enabled "$drive" && ! is_enabled "$unsafe"; then
    die "drive redirection requires QMT_RDP_ALLOW_UNSAFE_CHANNELS=1"
  fi

  case "$(printf '%s' "$clipboard" | tr '[:upper:]' '[:lower:]')" in
    none | 0 | no | false | off)
      set_ini_value "$XRDP_INI" Channels cliprdr false
      set_ini_value "$SESMAN_INI" Security RestrictOutboundClipboard all
      set_ini_value "$SESMAN_INI" Security RestrictInboundClipboard all
      ;;
    text | 1 | yes | true | on)
      set_ini_value "$XRDP_INI" Channels cliprdr true
      set_ini_value "$SESMAN_INI" Security RestrictOutboundClipboard file,image
      set_ini_value "$SESMAN_INI" Security RestrictInboundClipboard file,image
      ;;
    all)
      is_enabled "$unsafe" || die "QMT_RDP_CLIPBOARD=all requires QMT_RDP_ALLOW_UNSAFE_CHANNELS=1"
      set_ini_value "$XRDP_INI" Channels cliprdr true
      set_ini_value "$SESMAN_INI" Security RestrictOutboundClipboard none
      set_ini_value "$SESMAN_INI" Security RestrictInboundClipboard none
      ;;
    *) die "QMT_RDP_CLIPBOARD must be none, text, or all" ;;
  esac

  if is_enabled "$drive"; then
    set_ini_value "$XRDP_INI" Channels rdpdr true
    set_ini_value "$SESMAN_INI" Chansrv EnableFuseMount true
  else
    set_ini_value "$XRDP_INI" Channels rdpdr false
    set_ini_value "$SESMAN_INI" Chansrv EnableFuseMount false
  fi

  # Dynamic virtual channels carry display-resize messages. Audio, RemoteApp,
  # video, and smart-card-style peripheral channels are outside this appliance.
  set_ini_value "$XRDP_INI" Channels drdynvc true
  set_ini_value "$XRDP_INI" Channels rdpsnd false
  set_ini_value "$XRDP_INI" Channels rail false
  set_ini_value "$XRDP_INI" Channels xrdpvr false
}

[ -f "$XRDP_INI" ] || die "missing ${XRDP_INI}"
[ -f "$SESMAN_INI" ] || die "missing ${SESMAN_INI}"

getent group qmt-rdp >/dev/null || groupadd --system qmt-rdp
id "$USER_NAME" >/dev/null 2>&1 || die "desktop user ${USER_NAME} does not exist"
usermod -aG qmt-rdp "$USER_NAME"

provision_certificate

# The upstream installer creates a shared classic-RDP key at image build time.
# It is removed from the final image; generate a per-container compatibility key
# before startup even though policy below disables classic RDP negotiation.
if [ ! -s /etc/xrdp/rsakeys.ini ]; then
  umask 077
  /usr/bin/xrdp-keygen xrdp /etc/xrdp/rsakeys.ini >/dev/null
fi
chown root:xrdp /etc/xrdp/rsakeys.ini
chmod 0640 /etc/xrdp/rsakeys.ini
[ -s /etc/xrdp/rsakeys.ini ] || die "xrdp compatibility key generation failed"

set_ini_value "$XRDP_INI" Globals runtime_user xrdp
set_ini_value "$XRDP_INI" Globals runtime_group xrdp
set_ini_value "$XRDP_INI" Globals security_layer tls
set_ini_value "$XRDP_INI" Globals crypt_level high
set_ini_value "$XRDP_INI" Globals certificate "$CERT_FILE"
set_ini_value "$XRDP_INI" Globals key_file "$KEY_FILE"
set_ini_value "$XRDP_INI" Globals ssl_protocols 'TLSv1.2, TLSv1.3'
set_ini_value "$XRDP_INI" Globals autorun Xorg
set_ini_value "$XRDP_INI" Globals require_credentials true

set_ini_value "$SESMAN_INI" Security AllowRootLogin false
set_ini_value "$SESMAN_INI" Security MaxLoginRetry 3
set_ini_value "$SESMAN_INI" Security TerminalServerUsers qmt-rdp
set_ini_value "$SESMAN_INI" Security AlwaysGroupCheck true
set_ini_value "$SESMAN_INI" Security SessionSockdirGroup xrdp
set_ini_value "$SESMAN_INI" Sessions MaxSessions 1
set_ini_value "$SESMAN_INI" Sessions KillDisconnected false
set_ini_value "$SESMAN_INI" Sessions DisconnectedTimeLimit 0
set_ini_value "$SESMAN_INI" Sessions IdleTimeLimit 0
set_ini_value "$SESMAN_INI" Sessions Policy Default

configure_channels
log "TLS-only Xorg policy applied (single persistent session)"
