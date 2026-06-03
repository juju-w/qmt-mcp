#!/usr/bin/env bash
set -euo pipefail

export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"

if [ "$WINEARCH" != "wow64" ]; then
  echo "ERROR: this PoC requires WINEARCH=wow64 for Wine 11 new WoW64 mode on Apple Silicon." >&2
  exit 1
fi

if [ ! -d "$WINEPREFIX/drive_c" ]; then
  wineboot --init
  wineserver -w
fi

if [ -n "${WINE_APP:-}" ]; then
  exec wine "$WINE_APP"
fi

exec wine explorer
