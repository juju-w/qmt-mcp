"""ASGI application assembly for the official MCP Python SDK."""

from __future__ import annotations

import hmac
import json
import os
import sys
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from mcp.server import CacheHint, MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.subscriptions import InMemorySubscriptionBus
from mcp.shared.exceptions import MCPError
from mcp.types import ListToolsResult
from starlette.middleware.gzip import GZipMiddleware

from .audit import JsonlAuditSink
from .auth import build_token_verifier
from .config import CoreConfig, load_config
from .connector import TraderConnector
from .errors import McpCoreError, error_envelope
from .health import HealthState
from .pagination import InvalidPaginationCursor, paginate_by_key
from .readiness import ReadinessProbe
from .registry import ToolRegistry
from .runtime_paths import runtime_path
from .task_notifications import TaskListenHandler, TaskSubscriptionsListenRequestParams
from .task_store import TaskStore
from .tasks_extension import (
    TasksExtension,
    register_task_conformance_fixtures,
)
from .tool_contracts import ToolVisibilityPolicy
from .workers import WorkerPool

MODERN_PROTOCOL_VERSION = "2026-07-28"


def log(*parts: Any) -> None:
    print("[qmt-mcp]", *parts, file=sys.stderr, flush=True)


def _add_xtquant_path(config: CoreConfig) -> None:
    xtq = runtime_path(config.xtquant_dir_win)
    if xtq and xtq not in sys.path:
        sys.path.insert(0, xtq)


async def _json_response(
    send, status: int, payload: dict[str, Any], headers: list[tuple[bytes, bytes]] | None = None
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response_headers = [(b"content-type", b"application/json; charset=utf-8")]
    if headers:
        response_headers.extend(headers)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": response_headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


def _header_map(scope) -> dict[bytes, bytes]:
    return {name.lower(): value for name, value in (scope.get("headers") or [])}


def _base_url(scope, config: CoreConfig) -> str:
    if config.public_base_url:
        return config.public_base_url
    headers = _header_map(scope)
    host = headers.get(b"x-forwarded-host") or headers.get(b"host") or b""
    proto = headers.get(b"x-forwarded-proto") or scope.get("scheme", "http").encode()
    if host:
        return f"{proto.decode()}://{host.decode()}".rstrip("/")
    return f"http://{config.host}:{config.port}".rstrip("/")


def _resource_url(scope, config: CoreConfig) -> str:
    if config.oauth_resource_url:
        return config.oauth_resource_url
    return f"{_base_url(scope, config)}/mcp"


def _resource_metadata_url(scope, config: CoreConfig) -> str:
    resource = urlsplit(_resource_url(scope, config))
    suffix = resource.path.strip("/")
    metadata_path = "/.well-known/oauth-protected-resource"
    if suffix:
        metadata_path = f"{metadata_path}/{suffix}"
    return urlunsplit((resource.scheme, resource.netloc, metadata_path, "", ""))


def _protected_resource_metadata(scope, config: CoreConfig) -> dict[str, Any]:
    return {
        "resource": _resource_url(scope, config),
        "resource_name": config.oauth_resource_name,
        "authorization_servers": list(config.authorization_servers),
        "scopes_supported": list(config.oauth_scopes_supported),
        "bearer_methods_supported": ["header"],
    }


def _www_authenticate(scope, config: CoreConfig) -> str:
    if not config.oauth_enabled:
        return "Bearer"
    parts = [f'resource_metadata="{_resource_metadata_url(scope, config)}"']
    parts.append('scope="qmt:read"')
    parts.append(f'resource="{_resource_url(scope, config)}"')
    return "Bearer " + ", ".join(parts)


def _insufficient_scope_challenge(scope, config: CoreConfig, missing_scope: str) -> str:
    return (
        'Bearer error="insufficient_scope", '
        f'scope="{missing_scope}", '
        f'resource_metadata="{_resource_metadata_url(scope, config)}", '
        f'resource="{_resource_url(scope, config)}"'
    )


def _current_scopes() -> set[str] | None:
    token = get_access_token()
    return set(token.scopes) if token is not None else None


def _make_readiness_probe(config: CoreConfig, health: HealthState) -> ReadinessProbe:
    """Real signals: userdata_mini present (fs) + a cheap xtdata call (sdk)."""

    def fs_ready() -> bool:
        ud = config.userdata_win.strip()
        if not ud:
            return False
        return os.path.isdir(runtime_path(ud))

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
    def __init__(self, app, config: CoreConfig, health: HealthState, registry: ToolRegistry, token_verifier=None):
        self.app = app
        self.config = config
        self.health = health
        self.registry = registry
        self.token_verifier = token_verifier
        self.readiness_probe: ReadinessProbe | None = None
        self.connector: TraderConnector | None = None

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "lifespan":

            async def lifespan_receive():
                message = await receive()
                if message.get("type") == "lifespan.shutdown":
                    task_notifications = getattr(self, "task_notifications", None)
                    if task_notifications is not None:
                        task_notifications.close()
                return message

            await self.app(scope, lifespan_receive, send)
            return
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

        if path in {"/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"}:
            if not self.config.oauth_enabled:
                await _json_response(
                    send, 404, error_envelope("disabled", "OAuth protected resource metadata disabled")
                )
                return
            await _json_response(
                send,
                200,
                _protected_resource_metadata(scope, self.config),
                headers=[
                    (b"access-control-allow-origin", b"*"),
                    (b"cache-control", b"public, max-age=300"),
                ],
            )
            return

        headers = _header_map(scope)
        auth = headers.get(b"authorization", b"").decode()
        access_token = None
        if self.config.sdk_oauth_enabled:
            raw_token = auth[7:] if auth.lower().startswith("bearer ") else ""
            if raw_token and self.token_verifier is not None:
                access_token = await self.token_verifier.verify_token(raw_token)
            authorized = access_token is not None
        else:
            authorized = not self.config.auth_required or hmac.compare_digest(auth, f"Bearer {self.config.token}")
        if self.config.auth_required and not authorized:
            await _json_response(
                send,
                401,
                error_envelope("auth", "unauthorized"),
                headers=[(b"www-authenticate", _www_authenticate(scope, self.config).encode("utf-8"))],
            )
            return

        if access_token is not None and "qmt:read" not in access_token.scopes:
            await _json_response(
                send,
                403,
                error_envelope("insufficient_scope", "required scope: qmt:read"),
                headers=[
                    (
                        b"www-authenticate",
                        _insufficient_scope_challenge(scope, self.config, "qmt:read").encode("utf-8"),
                    )
                ],
            )
            return

        if access_token is not None and path == "/mcp" and headers.get(b"mcp-method", b"").decode() == "tools/call":
            tool_name = headers.get(b"mcp-name", b"").decode()
            required = self.registry.required_scopes(tool_name)
            granted = set(access_token.scopes)
            if required is not None and not self.registry.oauth_authorized(tool_name, granted):
                missing = next((item for item in required if item not in granted), "qmt:read")
                await _json_response(
                    send,
                    403,
                    error_envelope("insufficient_scope", f"required scope: {missing}"),
                    headers=[
                        (
                            b"www-authenticate",
                            _insufficient_scope_challenge(scope, self.config, missing).encode("utf-8"),
                        )
                    ],
                )
                return

        if path == "/healthz":
            await _json_response(send, 200, self.health.to_dict())
            return

        await self.app(scope, receive, send)


class ModernProtocolMiddleware:
    """Keep the public MCP endpoint on the stateless 2026-07-28 contract."""

    MAX_REJECTION_BODY = 1_048_576

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") != "/mcp":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        if method in {"GET", "DELETE"}:
            await _json_response(
                send,
                405,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32600,
                        "message": "Standalone MCP session methods are not supported",
                    },
                },
                headers=[(b"allow", b"POST")],
            )
            return
        if method != "POST":
            await self.app(scope, receive, send)
            return

        headers = _header_map(scope)
        requested = headers.get(b"mcp-protocol-version", b"").decode("utf-8", "replace").strip()
        if requested == MODERN_PROTOCOL_VERSION:
            await self.app(scope, receive, send)
            return

        request_id = await self._bounded_request_id(receive)
        await _json_response(
            send,
            400,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32022,
                    "message": "Unsupported MCP protocol version",
                    "data": {
                        "supported": [MODERN_PROTOCOL_VERSION],
                        "requested": requested,
                    },
                },
            },
        )

    async def _bounded_request_id(self, receive):
        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            body.extend(message.get("body", b""))
            more_body = message.get("more_body", False)
            if len(body) > self.MAX_REJECTION_BODY:
                return None
        try:
            document = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(document, Mapping):
            return None
        request_id = document.get("id")
        if isinstance(request_id, bool) or not isinstance(request_id, (str, int, float, type(None))):
            return None
        return request_id


def _accepts_gzip(value: str) -> bool:
    explicit: bool | None = None
    wildcard: bool | None = None
    for member in value.split(","):
        parts = [part.strip() for part in member.split(";")]
        coding = parts[0].lower()
        if not coding:
            continue
        quality = 1.0
        for parameter in parts[1:]:
            name, separator, raw_value = parameter.partition("=")
            if name.strip().lower() != "q" or not separator:
                continue
            try:
                quality = float(raw_value.strip())
            except ValueError:
                quality = 0.0
        accepted = 0.0 < quality <= 1.0
        if coding == "gzip":
            explicit = accepted
        elif coding == "*":
            wildcard = accepted
    return explicit if explicit is not None else bool(wildcard)


class NegotiatedGZipMiddleware:
    """Apply Starlette gzip only when HTTP quality negotiation permits it."""

    def __init__(self, app, minimum_size: int):
        self.app = app
        self.gzip_app = GZipMiddleware(app, minimum_size=minimum_size, compresslevel=6)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = _header_map(scope)
        if not _accepts_gzip(headers.get(b"accept-encoding", b"").decode("latin-1")):
            await self.app(scope, receive, send)
            return
        gzip_scope = dict(scope)
        gzip_scope["headers"] = [
            (name, value) for name, value in scope.get("headers", []) if name.lower() != b"accept-encoding"
        ]
        gzip_scope["headers"].append((b"accept-encoding", b"gzip"))
        await self.gzip_app(gzip_scope, receive, send)


class TaskRoutingHeaderMiddleware:
    """Validate SEP-2663 task routing names missing from SDK 2.0's core map."""

    METHODS = frozenset({"tasks/get", "tasks/update", "tasks/cancel"})
    MAX_BODY = 1_048_576

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path") != "/mcp":
            await self.app(scope, receive, send)
            return
        headers = _header_map(scope)
        header_method = headers.get(b"mcp-method", b"").decode("utf-8", "replace")
        if header_method not in self.METHODS:
            await self.app(scope, receive, send)
            return
        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            body.extend(message.get("body", b""))
            more_body = message.get("more_body", False)
            if len(body) > self.MAX_BODY:
                await _json_response(
                    send,
                    413,
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32600,
                            "message": "Task request exceeds 1 MiB",
                        },
                    },
                )
                return
        raw_body = bytes(body)
        try:
            document = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self.app(scope, self._replay(raw_body, receive), send)
            return
        method = document.get("method") if isinstance(document, Mapping) else None
        if method not in self.METHODS:
            await self.app(scope, self._replay(raw_body, receive), send)
            return
        params = document.get("params")
        task_id = params.get("taskId") if isinstance(params, Mapping) else None
        header_name = headers.get(b"mcp-name", b"").decode("utf-8", "replace")
        if header_method != method or not isinstance(task_id, str) or header_name != task_id:
            await _json_response(
                send,
                400,
                {
                    "jsonrpc": "2.0",
                    "id": document.get("id"),
                    "error": {
                        "code": -32020,
                        "message": "MCP routing headers do not match the request",
                    },
                },
            )
            return
        await self.app(scope, self._replay(raw_body, receive), send)

    @staticmethod
    def _replay(body: bytes, fallback):
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return await fallback()
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return receive


def register_core_tools(mcp: MCPServer, registry: ToolRegistry, health: HealthState) -> None:
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
        payload = health.capabilities()
        payload["tool_visibility"] = registry.visibility_summary(_current_scopes())
        return payload


class AuthorizedMCPServer(MCPServer):
    """Apply request-specific OAuth visibility on top of startup registration."""

    tool_registry: ToolRegistry | None = None

    def __init__(self, *args, tool_page_size: int = 50, **kwargs):
        self.tool_page_size = tool_page_size
        super().__init__(*args, **kwargs)

    async def list_tools(self):
        tools = await super().list_tools()
        token = get_access_token()
        if token is None or self.tool_registry is None:
            return tools
        allowed = set(self.tool_registry.oauth_tool_names(set(token.scopes)))
        return [tool for tool in tools if tool.name in allowed]

    async def _handle_list_tools(self, ctx, params):
        tools = await self.list_tools()
        cursor = params.cursor if params is not None else None
        try:
            page, next_cursor = paginate_by_key(
                tools,
                page_size=self.tool_page_size,
                cursor=cursor,
                key=lambda tool: tool.name,
            )
        except InvalidPaginationCursor as exc:
            raise MCPError(code=-32602, message="Invalid pagination cursor") from exc
        return ListToolsResult(tools=page, nextCursor=next_cursor)

    async def call_tool(self, name, arguments, context=None):
        token = get_access_token()
        if token is not None and self.tool_registry is not None:
            required = self.tool_registry.required_scopes(name)
            if required is not None and not self.tool_registry.oauth_authorized(name, set(token.scopes)):
                raise MCPError(
                    code=-32003,
                    message="Insufficient scope",
                    data={"required_scopes": list(required)},
                )
        return await super().call_tool(name, arguments, context)

    def install_task_notifications(self, tasks_extension: TasksExtension) -> TaskListenHandler:
        """Replace the core-only SDK listen handler with the Tasks-aware superset."""

        handler = TaskListenHandler(self._subscriptions, tasks_extension)
        self._lowlevel_server.add_request_handler(
            "subscriptions/listen",
            TaskSubscriptionsListenRequestParams,
            handler,
        )
        return handler


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
    mcp: MCPServer, registry: ToolRegistry, health: HealthState, config: CoreConfig, warehouse=None
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


def register_optional_apps(registry: ToolRegistry, health: HealthState, config: CoreConfig, warehouse=None):
    """Create UI extensions before MCPServer consumes extension contributions."""

    if not config.enable_xtdata or not registry.visibility.visible(
        name="qmt_xtdata_kline_chart", family="xtdata", read_only=True
    ):
        return None
    from qmt_mcp_apps.kline import register_kline_app

    return register_kline_app(registry, health, warehouse=warehouse)


def register_optional_xttrade(mcp: MCPServer, registry: ToolRegistry, health: HealthState, config: CoreConfig):
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
        session = TraderSession(runtime_path(config.userdata_win), allowlist)
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


def register_optional_portfolio(
    mcp: MCPServer, registry: ToolRegistry, health: HealthState, config: CoreConfig, trader_session=None
) -> None:
    if not config.enable_portfolio_analysis:
        health.set_family("portfolio", "disabled", "portfolio analysis disabled (QMT_ENABLE_PORTFOLIO_ANALYSIS=0)", [])
        return
    if trader_session is None:
        health.set_family("portfolio", "not_authorized", "requires enabled xttrade query with account allowlist", [])
        return
    try:
        from qmt_mcp_portfolio.tools import register_portfolio_tools

        register_portfolio_tools(mcp, registry, health, trader_session)
        health.set_family(
            "portfolio",
            "enabled",
            "read-only portfolio analysis enabled",
            registry.tool_names("portfolio"),
        )
    except Exception as exc:
        health.set_family("portfolio", "error", f"failed to register portfolio tools: {type(exc).__name__}", [])


def create_app(config: CoreConfig | None = None):
    config = config or load_config()
    config.validate_security()
    _add_xtquant_path(config)

    audit = JsonlAuditSink(config.audit_path, config.broker_id)
    health = HealthState(config)
    try:
        audit.initialize()
        health.audit = "ok"
    except McpCoreError:
        health.audit = "error"
        raise

    workers = WorkerPool(config.worker_limit)
    visibility = ToolVisibilityPolicy(config.tool_profile, config.tool_allowlist, config.tool_denylist)
    registry = ToolRegistry(health, audit, workers, visibility)
    warehouse = _make_warehouse(config, health)

    private_no_cache = CacheHint(ttl_ms=0, scope="private")
    subscriptions = InMemorySubscriptionBus()
    tasks_extension = None
    extensions = []
    if config.tasks_enabled:
        task_store = TaskStore(
            config.effective_task_store,
            ttl_ms=config.task_ttl_ms,
            poll_interval_ms=config.task_poll_interval_ms,
            max_retained=config.task_max_retained,
        )
        task_store.recover_interrupted()
        task_tools = list(config.task_tools)
        mrtr_before_task_tools = []
        if config.task_conformance_fixtures:
            task_tools.extend(
                (
                    "slow_compute",
                    "failing_job",
                    "protocol_error_job",
                    "confirm_delete",
                    "multi_input",
                    "test_tool_with_task",
                )
            )
            mrtr_before_task_tools.append("test_tool_with_task")
        tasks_extension = TasksExtension(
            task_store,
            task_tools=task_tools,
            mrtr_before_task_tools=mrtr_before_task_tools,
            conformance_fixtures=config.task_conformance_fixtures,
            subscriptions=subscriptions,
        )
        extensions.append(tasks_extension)
    apps_extension = register_optional_apps(registry, health, config, warehouse=warehouse)
    if apps_extension is not None:
        extensions.append(apps_extension)
    token_verifier = build_token_verifier(config) if config.sdk_oauth_enabled else None
    auth_settings = None
    if config.sdk_oauth_enabled:
        auth_settings = AuthSettings(
            issuer_url=config.oauth_issuer_url,
            required_scopes=["qmt:read"],
            resource_server_url=config.oauth_resource_url,
        )
    mcp = AuthorizedMCPServer(
        "QMT MCP",
        tool_page_size=config.mcp_list_page_size,
        version=os.environ.get("QMT_MCP_VERSION", "dev"),
        cache_hints={
            "server/discover": private_no_cache,
            "tools/list": private_no_cache,
            "prompts/list": private_no_cache,
            "resources/list": private_no_cache,
            "resources/templates/list": private_no_cache,
            "resources/read": private_no_cache,
        },
        auth=auth_settings,
        token_verifier=token_verifier,
        extensions=extensions,
        subscriptions=subscriptions,
    )
    task_notifications = None
    if tasks_extension is not None:
        task_notifications = mcp.install_task_notifications(tasks_extension)
    mcp.tool_registry = registry
    if tasks_extension is not None:
        tasks_extension.bind_registry(registry)
    register_core_tools(mcp, registry, health)
    register_optional_xtdata(mcp, registry, health, config, warehouse=warehouse)
    trader_session = register_optional_xttrade(mcp, registry, health, config)
    register_optional_portfolio(mcp, registry, health, config, trader_session=trader_session)
    if config.task_conformance_fixtures:
        register_task_conformance_fixtures(mcp)
    registry.assert_no_write_tools()

    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        host=config.host,
    )
    app = ModernProtocolMiddleware(app)
    if config.tasks_enabled:
        app = TaskRoutingHeaderMiddleware(app)
    if config.mcp_gzip_minimum_size > 0:
        app = NegotiatedGZipMiddleware(app, config.mcp_gzip_minimum_size)
    core = CoreASGI(app, config, health, registry, token_verifier)
    core.tasks_extension = tasks_extension
    core.task_notifications = task_notifications
    core.apps_extension = apps_extension
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
        f"transport={config.transport} auth={config.auth_mode if config.auth_required else 'loopback-dev'} "
        f"audit={config.audit_path} "
        f"tool_profile={config.tool_profile} tools={registry.tool_names()}"
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
