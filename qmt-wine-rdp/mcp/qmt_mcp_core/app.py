"""ASGI/FastMCP application assembly."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from fastmcp import FastMCP

from .audit import JsonlAuditSink
from .config import CoreConfig, load_config
from .errors import McpCoreError, error_envelope
from .health import HealthState
from .registry import ToolRegistry
from .workers import WorkerPool


def log(*parts: Any) -> None:
    print("[qmt-mcp]", *parts, file=sys.stderr, flush=True)


def _add_xtquant_path(config: CoreConfig) -> None:
    xtq = config.xtquant_dir_win.strip()
    if xtq and xtq not in sys.path:
        sys.path.insert(0, xtq)


async def _json_response(send, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json; charset=utf-8")],
    })
    await send({"type": "http.response.body", "body": body})


class CoreASGI:
    def __init__(self, app, config: CoreConfig, health: HealthState):
        self.app = app
        self.config = config
        self.health = health

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode()
        if self.config.auth_required and auth != f"Bearer {self.config.token}":
            await _json_response(send, 401, error_envelope("auth", "unauthorized"))
            return

        if path == "/healthz":
            await _json_response(send, 200, self.health.to_dict())
            return

        await self.app(scope, receive, send)


def register_core_tools(mcp: FastMCP, registry: ToolRegistry, health: HealthState) -> None:
    @registry.register(
        mcp,
        name="qmt_health",
        family="core",
        description="Return the QMT MCP server health and dependency capability state.",
    )
    def qmt_health() -> dict[str, Any]:
        return health.to_dict()

    @registry.register(
        mcp,
        name="qmt_capabilities",
        family="core",
        description="Return enabled, disabled, not-ready, and not-authorized MCP tool family states.",
    )
    def qmt_capabilities() -> dict[str, Any]:
        return health.capabilities()


def register_optional_xtdata(mcp: FastMCP, registry: ToolRegistry, health: HealthState, config: CoreConfig) -> None:
    if not config.enable_xtdata:
        health.xtdata = "disabled"
        health.set_family("xtdata", "disabled", "xtdata tools disabled by config", [])
        return
    try:
        from qmt_mcp_xtdata.tools import register_xtdata_tools

        register_xtdata_tools(mcp, registry, health)
    except Exception as exc:
        health.xtdata = "error"
        health.set_family("xtdata", "error", f"failed to register xtdata tools: {type(exc).__name__}", [])


def create_app(config: CoreConfig | None = None):
    config = config or load_config()
    _add_xtquant_path(config)

    audit = JsonlAuditSink(config.audit_path, config.broker_id)
    health = HealthState(config)
    try:
        audit.initialize()
        health.audit = "ok"
    except McpCoreError:
        health.audit = "error"
        raise

    mcp = FastMCP("QMT MCP")
    workers = WorkerPool(config.worker_limit)
    registry = ToolRegistry(health, audit, workers)
    register_core_tools(mcp, registry, health)
    register_optional_xtdata(mcp, registry, health, config)
    registry.assert_no_write_tools()

    app = mcp.http_app(transport="sse")
    return CoreASGI(app, config, health), config, health, registry


def main() -> None:
    app, config, health, registry = create_app()
    log(
        f"broker={config.broker_id} mode={config.mcp_mode} host={config.host}:{config.port} "
        f"auth={'on' if config.auth_required else 'loopback-dev'} audit={config.audit_path} "
        f"tools={registry.tool_names()}"
    )
    import uvicorn

    uvicorn.run(app, host=config.host, port=config.port, log_level=os.environ.get("QMT_MCP_LOG_LEVEL", "info"))
