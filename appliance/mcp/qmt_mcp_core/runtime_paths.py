"""Translate configured QMT paths for the Python runtime that consumes them."""

from __future__ import annotations

import ntpath
import os


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
