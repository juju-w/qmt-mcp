#!/usr/bin/env bash
set -euo pipefail

PY_VERSION="${1:-3.12.10}"
PY_MAJOR_MINOR="$(printf '%s' "$PY_VERSION" | awk -F. '{print $1 "." $2}')"
PY_SHORT="$(printf '%s' "$PY_VERSION" | awk -F. '{print $1 $2}')"
PY_INSTALL_DIR="C:\\Python${PY_SHORT}"
DOWNLOAD_DIR="${DOWNLOAD_DIR:-/workspace/python/downloads}"
INSTALLER="${DOWNLOAD_DIR}/python-${PY_VERSION}-amd64.exe"
PY_URL="https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-amd64.exe"

export WINEARCH="${WINEARCH:-wow64}"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"

if [ "$WINEARCH" != "wow64" ]; then
  echo "ERROR: this PoC requires WINEARCH=wow64 for Wine 11 new WoW64 mode on Apple Silicon." >&2
  exit 1
fi

mkdir -p "$DOWNLOAD_DIR"

if [ ! -f "$INSTALLER" ]; then
  echo "Downloading Windows Python ${PY_VERSION} x64..."
  curl -fL "$PY_URL" -o "$INSTALLER"
fi

echo "Installing Windows Python ${PY_VERSION} to ${PY_INSTALL_DIR}..."
wine "$INSTALLER" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 TargetDir="$PY_INSTALL_DIR"
wineserver -w

echo "Verifying Windows Python ${PY_MAJOR_MINOR}..."
wine "${PY_INSTALL_DIR}\\python.exe" --version
