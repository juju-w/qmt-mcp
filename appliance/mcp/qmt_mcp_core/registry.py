"""Explicit MCP tool registry with audit wrappers."""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from typing import Any

from .audit import JsonlAuditSink, request_id
from .errors import McpCoreError, error_envelope, from_exception
from .health import HealthState
from .tool_contracts import (
    ToolBehavior,
    ToolVisibilityPolicy,
    default_tool_title,
    mutation_like,
    register_mcp_tool,
)
from .workers import WorkerPool

# Write/trade VERBS that must never be exposed. Matched as substrings of the tool
# name. Deliberately precise so read-only listings are not false-positives:
#   - "orders" (a listing) must pass; only "order_stock"/"place_order"/"passorder"
#     (placement) are blocked.
#   - credit/smt READ queries (slo/compact/negotiate) are NOT write tools.
WRITE_TOOL_KEYWORDS = (
    "place_order",
    "order_stock",
    "order_credit",
    "passorder",
    "cancel",
    "transfer",
    "borrow",
    "export",
    "buy",
    "sell",
)


class ToolRegistry:
    def __init__(
        self,
        health: HealthState,
        audit: JsonlAuditSink,
        workers: WorkerPool,
        visibility: ToolVisibilityPolicy | None = None,
    ):
        self.health = health
        self.audit = audit
        self.workers = workers
        self.visibility = visibility or ToolVisibilityPolicy()
        self._tools: dict[str, dict[str, Any]] = {}

    def tool_names(self, family: str | None = None, *, visible_only: bool = True) -> list[str]:
        names = []
        for name, meta in self._tools.items():
            if (family is None or meta["family"] == family) and (not visible_only or meta["visible"]):
                names.append(name)
        return sorted(names)

    def visibility_summary(self) -> dict[str, Any]:
        visible = sum(1 for meta in self._tools.values() if meta["visible"])
        return {
            "profile": self.visibility.profile,
            "allowlist": list(self.visibility.allowlist),
            "denylist": list(self.visibility.denylist),
            "visible_count": visible,
            "hidden_count": len(self._tools) - visible,
        }

    def assert_no_write_tools(self) -> None:
        leaked = [name for name in self._tools if any(keyword in name.lower() for keyword in WRITE_TOOL_KEYWORDS)]
        if leaked:
            raise McpCoreError("internal", "write-capable tool names are not allowed", {"tools": leaked})

    def register(
        self,
        mcp: Any,
        *,
        name: str,
        family: str,
        description: str,
        audit_fields: list[str] | None = None,
        worker_backed: bool = False,
        timeout: float | None = None,
        title: str | None = None,
        read_only: bool = True,
        destructive: bool = False,
        idempotent: bool = True,
        open_world: bool | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            if name in self._tools:
                raise McpCoreError("internal", f"duplicate tool registered: {name}")
            if read_only and mutation_like(name):
                raise McpCoreError(
                    "internal",
                    "mutation-like tool must not be annotated read-only",
                    {"tool": name},
                )
            tool_title = title or default_tool_title(name)
            behavior = ToolBehavior(
                read_only=read_only,
                destructive=destructive,
                idempotent=idempotent,
                open_world=family != "core" if open_world is None else open_world,
            )
            visible = self.visibility.visible(name=name, family=family, read_only=read_only)

            @functools.wraps(func)
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                rid = request_id()
                started = time.time()
                arg_summary = self._summarize_args(func, args, kwargs, audit_fields)
                try:
                    if worker_backed:
                        result = self.workers.run_sync(func, *args, timeout=timeout, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    latency = int((time.time() - started) * 1000)
                    self.audit.append(
                        request_id_value=rid,
                        tool=name,
                        family=family,
                        args_summary=arg_summary,
                        outcome="ok" if not (isinstance(result, dict) and result.get("ok") is False) else "error",
                        error_type=result.get("error_type") if isinstance(result, dict) else None,
                        latency_ms=latency,
                    )
                    return result
                except McpCoreError as exc:
                    latency = int((time.time() - started) * 1000)
                    self.audit.append(
                        request_id_value=rid,
                        tool=name,
                        family=family,
                        args_summary=arg_summary,
                        outcome="refused",
                        error_type=exc.error_type,
                        latency_ms=latency,
                    )
                    return error_envelope(exc.error_type, exc.message, exc.details)
                except Exception as exc:  # pragma: no cover - defensive boundary
                    latency = int((time.time() - started) * 1000)
                    self.audit.append(
                        request_id_value=rid,
                        tool=name,
                        family=family,
                        args_summary=arg_summary,
                        outcome="error",
                        error_type="internal",
                        latency_ms=latency,
                    )
                    return from_exception(exc)

            wrapped.__name__ = name
            wrapped.__doc__ = description
            mcp_callable = None
            if visible:
                mcp_callable = register_mcp_tool(
                    mcp,
                    wrapped=wrapped,
                    name=name,
                    title=tool_title,
                    description=description,
                    behavior=behavior,
                )
            self._tools[name] = {
                "family": family,
                "title": tool_title,
                "description": description,
                "behavior": behavior,
                "visible": visible,
                "callable": wrapped,
                "mcp_callable": mcp_callable,
            }
            self.health.update_family_tools(family, self.tool_names(family))
            return wrapped

        return decorator

    @staticmethod
    def _summarize_args(
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        audit_fields: list[str] | None,
    ) -> dict[str, Any]:
        try:
            bound = inspect.signature(func).bind_partial(*args, **kwargs)
            raw = dict(bound.arguments)
        except Exception:
            raw = dict(kwargs)
        if audit_fields is None:
            return raw
        return {field: raw.get(field) for field in audit_fields if field in raw}
