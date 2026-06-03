"""ASGI/FastMCP application assembly."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from fastmcp import FastMCP

from .audit import JsonlAuditSink
from .config import CoreConfig, load_config
from .connector import TraderConnector
from .errors import McpCoreError, error_envelope
from .health import HealthState
from .readiness import ReadinessProbe
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
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _win_to_unix(win_path: str) -> str:
    """Heuristic Wine-path -> unix-path (Z:\\broker\\x -> /broker/x). Z: maps to /."""
    p = win_path.strip().replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        p = p[2:]  # drop the drive letter; Z: is the wine root (/)
    return p or "/"


def _make_readiness_probe(config: CoreConfig, health: HealthState) -> ReadinessProbe:
    """Real signals: userdata_mini present (fs) + a cheap xtdata call (sdk)."""

    def fs_ready() -> bool:
        ud = config.userdata_win.strip()
        if not ud:
            return False
        return os.path.isdir(_win_to_unix(ud))

    def sdk_ready() -> bool:
        from xtquant import xtdata  # type: ignore

        dates = xtdata.get_trading_dates("SH")
        return bool(dates)

    return ReadinessProbe(health, fs_ready=fs_ready, sdk_ready=sdk_ready, poll_s=config.readiness_poll_s)


def _make_connector(config: CoreConfig, health: HealthState, session=None) -> TraderConnector:
    """Build the 005 trader connector. When 004 supplies a TraderSession, use its
    real xttrader handshake; otherwise a scaffold that reports not_authorized (no
    account-query family enabled / no broker permission)."""
    if session is not None:
        connect_fn = session.connect
        is_connected = session.is_connected
    else:

        def connect_fn() -> str:
            return "not_authorized"

        is_connected = None

    return TraderConnector(
        health,
        connect_fn=connect_fn,
        is_logged_in=lambda: health.qmt_login == "logged_in",
        is_connected=is_connected,
        max_retry=config.connect_retry,
        backoff_max=config.connect_backoff_max_s,
    )


class CoreASGI:
    def __init__(self, app, config: CoreConfig, health: HealthState):
        self.app = app
        self.config = config
        self.health = health
        self.readiness_probe: ReadinessProbe | None = None
        self.connector: TraderConnector | None = None

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""

        # /livez is unauthenticated and detail-free (orchestration has no token).
        # It MUST be handled before the auth gate. It discloses only liveness.
        if path == "/livez":
            doc = self.health.livez()
            await _json_response(send, 200 if doc.get("ok") else 503, doc)
            return

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


def _make_warehouse(config: CoreConfig, health: HealthState):
    """Build the market-data warehouse when a DB is configured; else None.

    Fail-safe: any DB init error leaves health.database=error and returns None, so
    the appliance keeps working on the file/xtdata path (no DB required)."""
    if not config.db_enabled:
        health.database = "disabled"
        return None
    try:
        from qmt_mcp_db.engine import DbEngine
        from qmt_mcp_db.migrations import apply_migrations
        from qmt_mcp_db.warehouse import Warehouse

        engine = DbEngine(config.db_url, max_size=config.db_pool_max)
        engine.connect()
        apply_migrations(engine)
        health.database = "connected"
        if config.db_marketdata:
            health.db_domains = ["marketdata"]
            return Warehouse(engine, config.broker_id)
        health.db_domains = []
        return None
    except Exception as exc:
        health.database = "error"
        health.last_error = f"db init failed: {type(exc).__name__}"  # never include the DSN
        return None


def register_optional_xtdata(
    mcp: FastMCP, registry: ToolRegistry, health: HealthState, config: CoreConfig, warehouse=None
) -> None:
    if not config.enable_xtdata:
        health.xtdata = "disabled"
        health.set_family("xtdata", "disabled", "xtdata tools disabled by config", [])
        return
    try:
        from qmt_mcp_xtdata.tools import register_xtdata_tools

        register_xtdata_tools(mcp, registry, health, warehouse=warehouse)
    except Exception as exc:
        health.xtdata = "error"
        health.set_family("xtdata", "error", f"failed to register xtdata tools: {type(exc).__name__}", [])


def register_optional_xttrade(mcp: FastMCP, registry: ToolRegistry, health: HealthState, config: CoreConfig):
    """Register the read-only account-query family iff enabled + allow-listed.

    Returns a TraderSession (for the connector) when registered, else None. Fails
    closed: enabled-but-no-allowlist does NOT expose any account tool.
    """
    if not config.enable_xttrade_query:
        health.set_family("xttrade_query", "disabled", "account-query disabled (QMT_ENABLE_XTTRADE_QUERY=0)", [])
        return None
    try:
        from qmt_mcp_xttrade.accounts import Allowlist
        from qmt_mcp_xttrade.session import TraderSession
        from qmt_mcp_xttrade.tools import register_xttrade_tools

        allowlist = Allowlist.from_config(config.trade_accounts, config.trade_account_type)
        if not allowlist:
            health.set_family(
                "xttrade_query", "disabled", "enabled but no QMT_TRADE_ACCOUNTS allowlist — refusing (fail-closed)", []
            )
            return None
        session = TraderSession(_win_to_unix(config.userdata_win), allowlist)
        register_xttrade_tools(mcp, registry, health, session, allowlist)
        health.set_family(
            "xttrade_query",
            "enabled",
            f"read-only account-query enabled for {len(allowlist.ids())} allow-listed account(s)",
            registry.tool_names("xttrade_query"),
        )
        return session
    except Exception as exc:
        health.set_family("xttrade_query", "error", f"failed to register account-query tools: {type(exc).__name__}", [])
        return None


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
    warehouse = _make_warehouse(config, health)
    register_optional_xtdata(mcp, registry, health, config, warehouse=warehouse)
    trader_session = register_optional_xttrade(mcp, registry, health, config)
    registry.assert_no_write_tools()

    app = mcp.http_app(transport=config.transport)
    core = CoreASGI(app, config, health)
    # Build (do not start) the background readiness probe / trader connector.
    # main() starts them; tests can drive .step()/.attempt() directly.
    if config.enable_xtdata:
        core.readiness_probe = _make_readiness_probe(config, health)
    core.connector = _make_connector(config, health, session=trader_session)
    return core, config, health, registry


def main() -> None:
    app, config, health, registry = create_app()
    log(
        f"broker={config.broker_id} mode={config.mcp_mode} host={config.host}:{config.port} "
        f"transport={config.transport} auth={'on' if config.auth_required else 'loopback-dev'} audit={config.audit_path} "
        f"tools={registry.tool_names()}"
    )
    # Start background readiness probe (always when xtdata is enabled) and the
    # trader connector. The connector runs when explicitly enabled OR when the
    # account-query family (004) is on (it needs the session connected). Both are
    # daemon threads and never block serving.
    if app.readiness_probe is not None:
        app.readiness_probe.start()
        log("readiness probe started")
    if (config.enable_connector or config.enable_xttrade_query) and app.connector is not None:
        app.connector.start()
        log("trader connector started")
    else:
        log("trader connector disabled (set QMT_ENABLE_CONNECTOR=1 or QMT_ENABLE_XTTRADE_QUERY=1)")

    import uvicorn

    uvicorn.run(app, host=config.host, port=config.port, log_level=os.environ.get("QMT_MCP_LOG_LEVEL", "info"))
