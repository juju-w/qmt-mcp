#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:10}"
export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
export QT_OPENGL="${QT_OPENGL:-software}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export QTWEBENGINE_DISABLE_SANDBOX="${QTWEBENGINE_DISABLE_SANDBOX:-1}"

qmt_dir="${QMT_BIN_DIR:-/workspace/QMT/extracted/bin.x64}"
qmt_exe="${QMT_EXE:-XtItClient.exe}"

if [ "$WINEARCH" != "wow64" ]; then
  echo "ERROR: this PoC requires WINEARCH=wow64 for Wine 11 new WoW64 mode on Apple Silicon." >&2
  exit 1
fi

cd "$qmt_dir"
exec wine "$qmt_exe"
