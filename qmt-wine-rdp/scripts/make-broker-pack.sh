#!/usr/bin/env bash
# Build a broker pack from a broker's QMT installer + a matching xtquant archive.
#
#   make-broker-pack.sh <setup_qmt.exe> <xtquant.(rar|zip)> <out-dir> [broker-id]
#
# Produces:
#   <out-dir>/<extracted QMT terminal tree, incl. bin.x64/XtItClient.exe>
#   <out-dir>/xtquant/                (the matching xtquant package)
#   <out-dir>/broker.yaml             (starter config; auto-detection-friendly)
#
# Requires 7z (p7zip-full) for the NSIS installer and unrar (RARLAB) for RAR5
# xtquant. Run on any linux/amd64 host with those tools.
set -euo pipefail

SETUP="${1:?usage: make-broker-pack.sh <setup_qmt.exe> <xtquant.rar|zip> <out-dir> [broker-id]}"
XTQ="${2:?missing xtquant archive (rar/zip)}"
OUT="${3:?missing out-dir}"
BROKER_ID="${4:-$(basename "$OUT")}"

command -v 7z   >/dev/null || { echo "ERROR: 7z (p7zip-full) not found" >&2; exit 1; }

mkdir -p "$OUT"
echo "[make-pack] extracting QMT terminal -> $OUT"
7z x -y "$SETUP" -o"$OUT" >/dev/null
test -n "$(find "$OUT" -iname 'XtItClient.exe' -o -iname 'XtMiniQmt.exe' | head -1)" \
  || { echo "ERROR: no QMT client found after extracting $SETUP" >&2; exit 1; }

echo "[make-pack] extracting xtquant -> $OUT/xtquant"
case "$XTQ" in
  *.rar|*.RAR)
    command -v unrar >/dev/null || { echo "ERROR: unrar (RARLAB) required for RAR5 xtquant" >&2; exit 1; }
    unrar x -y "$XTQ" "$OUT/" >/dev/null ;;
  *.zip|*.ZIP)
    unzip -o -q "$XTQ" -d "$OUT" ;;
  *) echo "ERROR: unsupported xtquant archive: $XTQ" >&2; exit 1 ;;
esac
XTQ_PKG="$(find "$OUT" -maxdepth 3 -type d -name xtquant -exec test -f '{}/__init__.py' ';' -print | head -1)"
test -n "$XTQ_PKG" || { echo "ERROR: no importable xtquant package after extracting $XTQ" >&2; exit 1; }

# Prefer XtItClient.exe; fall back to XtMiniQmt.exe. Pin it in broker.yaml so the
# pack is self-describing (real QMT trees ship several client-named exes).
CLIENT="$(find "$OUT" -iname 'XtItClient.exe' | head -1)"
[ -n "$CLIENT" ] || CLIENT="$(find "$OUT" -iname 'XtMiniQmt.exe' | head -1)"
CLIENT_REL="${CLIENT#"$OUT"/}"
XTQ_REL="${XTQ_PKG#"$OUT"/}"

if [ ! -f "$OUT/broker.yaml" ]; then
  echo "[make-pack] writing starter broker.yaml (client + xtquant pinned)"
  cat > "$OUT/broker.yaml" <<YAML
schema_version: 1
broker:
  id: ${BROKER_ID}
terminal:
  client: ${CLIENT_REL}
xtquant:
  path: ${XTQ_REL}
mcp:
  mode: readonly
YAML
fi

echo "[make-pack] done."
echo "  client : $CLIENT"
echo "  xtquant: $XTQ_PKG"
echo "  config : $OUT/broker.yaml"
