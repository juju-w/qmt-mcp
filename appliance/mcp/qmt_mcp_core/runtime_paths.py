"""Translate configured QMT paths for the Python runtime that consumes them."""

from __future__ import annotations

import ntpath
import os
import sys
from collections.abc import MutableSequence


def runtime_path(configured_path: str, platform_name: str | None = None) -> str:
    """Return a path usable by native/Wine Windows Python or POSIX Python.

    QMT paths are configured in Windows form. Native Windows and Wine-hosted
    Windows Python understand those paths directly. POSIX helpers retain the
    appliance's historical ``Z:\\...`` to ``/...`` conversion.
    """

    value = configured_path.strip()
    if not value:
        return ""
    if (platform_name or os.name) == "nt":
        return ntpath.normpath(value)

    value = value.replace("\\", "/")
    if len(value) >= 2 and value[1] == ":":
        value = value[2:]
    return value or "/"


def append_runtime_path(
    configured_path: str,
    search_path: MutableSequence[str] | None = None,
    platform_name: str | None = None,
) -> str:
    """Append a broker SDK path after the packaged runtime dependencies."""

    resolved = runtime_path(configured_path, platform_name)
    if not resolved:
        return ""
    paths = sys.path if search_path is None else search_path
    while resolved in paths:
        paths.remove(resolved)
    # Broker directories may contain NumPy/Pandas wheels for an older Python.
    # Appending keeps the packaged 3.11 dependencies authoritative.
    paths.append(resolved)
    return resolved
