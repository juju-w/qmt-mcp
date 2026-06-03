"""Production MCP core for the QMT appliance.

Re-exports are lazy (PEP 562) so importing pure-logic submodules
(`config`, `health`, `errors`, `audit`, `workers`, `registry`, ...) does not pull
in `fastmcp`/`uvicorn`. This keeps the bulk of the package testable on a plain
Python 3.12 with no third-party installs. `create_app`/`main` still resolve via
attribute access (they import `fastmcp` only when actually used).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["ToolRegistry", "create_app", "main"]

if TYPE_CHECKING:  # for type checkers only; not executed at runtime
    from .app import create_app, main
    from .registry import ToolRegistry


def __getattr__(name: str) -> Any:
    if name in {"create_app", "main"}:
        from . import app

        return getattr(app, name)
    if name == "ToolRegistry":
        from .registry import ToolRegistry

        return ToolRegistry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
