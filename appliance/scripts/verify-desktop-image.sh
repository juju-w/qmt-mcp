#!/usr/bin/env bash
# CI/runtime image gate for the patched xrdp foundation. No broker pack needed.
set -euo pipefail

fail() { printf '[desktop-image] FAIL: %s\n' "$*" >&2; exit 1; }
pass() { printf '[desktop-image] ok: %s\n' "$*"; }

[ "$(cat /usr/share/qmt/xrdp.version)" = "0.10.6.1" ] || fail "unexpected xrdp pin"
[ "$(cat /usr/share/qmt/xorgxrdp.version)" = "0.10.5" ] || fail "unexpected xorgxrdp pin"
/usr/sbin/xrdp --version 2>&1 | grep -Fq '0.10.6.1' || fail "xrdp binary version mismatch"
pass "xrdp 0.10.6.1 and xorgxrdp 0.10.5 pins"

if dpkg-query -W -f='${Status}' xrdp xorgxrdp 2>/dev/null | grep -q 'install ok installed'; then
  fail "obsolete distro xrdp package metadata remains installed"
fi
command -v gcc >/dev/null 2>&1 && fail "compiler leaked into runtime image"
pass "source build is isolated from runtime"

for binary in /usr/sbin/xrdp /usr/sbin/xrdp-sesman /usr/lib/xorg/modules/libxorgxrdp.so; do
  [ -e "$binary" ] || fail "missing ${binary}"
  if ldd "$binary" | grep -q 'not found'; then
    ldd "$binary" >&2
    fail "unresolved dependency in ${binary}"
  fi
done
ldd /usr/sbin/xrdp | grep -q 'libssl' || fail "xrdp lacks TLS linkage"
pass "xrdp, sesman, xorgxrdp, and TLS linkage"

grep -Fxq 'security_layer=tls' /etc/xrdp/xrdp.ini || fail "TLS-only policy missing"
grep -Fxq 'ssl_protocols=TLSv1.2, TLSv1.3' /etc/xrdp/xrdp.ini || fail "TLS floor missing"
grep -Fxq 'rdpdr=false' /etc/xrdp/xrdp.ini || fail "drive channel is not closed"
grep -Fxq 'cliprdr=false' /etc/xrdp/xrdp.ini || fail "clipboard is not closed"
grep -Fxq 'AllowRootLogin=false' /etc/xrdp/sesman.ini || fail "root login is not disabled"
grep -Fxq 'AlwaysGroupCheck=true' /etc/xrdp/sesman.ini || fail "login group is not enforced"
grep -Fxq 'MaxSessions=1' /etc/xrdp/sesman.ini || fail "session count is not bounded"
pass "TLS, authorization, channel, and session policy"

groups wineuser | tr ' ' '\n' | grep -Fxq sudo && fail "wineuser belongs to sudo"
for private_key in /var/lib/qmt-rdp/key.pem /etc/xrdp/key.pem /etc/xrdp/rsakeys.ini; do
  [ ! -e "$private_key" ] || fail "RDP private key is baked into image: ${private_key}"
done
pass "desktop user and runtime certificate boundary"
