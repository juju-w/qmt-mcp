"""Uniform client-facing error helpers."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any

ERROR_TYPES = {
    "validation",
    "auth",
    "config",  # startup-only: invalid runtime config (e.g. bad transport)
    "not_ready",
    "not_authorized",
    "disabled",
    "capacity",
    "dependency",
    "persistence",
    "internal",
}


@dataclass
class McpCoreError(Exception):
    error_type: str
    message: str
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.error_type not in ERROR_TYPES:
            self.error_type = "internal"
        super().__init__(self.message)


def error_envelope(
    error_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if error_type not in ERROR_TYPES:
        error_type = "internal"
    return {
        "ok": False,
        "error_type": error_type,
        "error": str(message),
        "details": details or {},
    }


def ok_envelope(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


def from_exception(exc: BaseException, *, expose_message: bool = True) -> dict[str, Any]:
    if isinstance(exc, McpCoreError):
        return error_envelope(exc.error_type, exc.message, exc.details)
    message = f"{type(exc).__name__}: {exc}" if expose_message else "internal error"
    return error_envelope("internal", message)


def stack_summary(exc: BaseException) -> str:
    return "".join(traceback.format_exception_only(type(exc), exc)).strip()
