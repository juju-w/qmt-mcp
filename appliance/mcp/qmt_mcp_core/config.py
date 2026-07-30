"""Runtime config loading for the MCP core."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import McpCoreError

DEFAULT_MCP_ENV = Path("/opt/qmt-mcp/mcp.env")
VALID_AUTH_MODES = frozenset({"static", "oauth", "hybrid"})
SAFE_JWT_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512"})
DEFAULT_OAUTH_SCOPES = ("qmt:read", "qmt:market", "qmt:account", "qmt:manage", "qmt:admin")
DEFAULT_TASK_TOOLS = (
    "qmt_xtdata_download_history",
    "qmt_xtdata_download_history_batch",
    "qmt_xtdata_download_financial_data",
    "qmt_xtdata_formula_call_batch",
    "qmt_xtdata_formula_generate_factor",
    "qmt_xtdata_refresh_instrument_cache",
)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        try:
            parsed = shlex.split(value, posix=True)
            result[key] = parsed[0] if parsed else ""
        except ValueError:
            result[key] = value.strip().strip("'\"")
    return result


def _merged_env(mcp_env_path: Path = DEFAULT_MCP_ENV) -> dict[str, str]:
    merged = _read_env_file(mcp_env_path)
    merged.update({k: v for k, v in os.environ.items()})
    return merged


def _is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or "").split(",") if part.strip())


def _split_scopes(value: str) -> tuple[str, ...]:
    normalized = (value or "").replace(",", " ")
    return tuple(part.strip() for part in normalized.split() if part.strip())


def _is_secure_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme == "https":
        return bool(parsed.netloc)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class CoreConfig:
    broker_id: str
    broker_name: str
    xtquant_dir_win: str
    userdata_win: str
    mcp_mode: str
    token: str
    host: str
    port: int
    transport: str
    audit_path: str
    worker_limit: int
    allow_unauth_loopback: bool
    enable_xtdata: bool
    test_mode: bool
    # 022 bounded MCP catalog pages and negotiated HTTP gzip.
    mcp_list_page_size: int = 50
    mcp_gzip_minimum_size: int = 1024
    # 023 stable MCP Tasks lifecycle for selected long-running tools.
    tasks_enabled: bool = True
    task_store: str = ""
    task_ttl_ms: int = 86_400_000
    task_poll_interval_ms: int = 1000
    task_max_retained: int = 1000
    task_tools: tuple[str, ...] = DEFAULT_TASK_TOOLS
    task_conformance_fixtures: bool = False
    # 005 readiness/connector knobs (defaults so direct construction stays easy).
    readiness_poll_s: float = 5.0
    enable_connector: bool = False
    connect_retry: int = 8
    connect_backoff_max_s: float = 60.0
    # 004 read-only account-query family (off by default; needs an allowlist).
    enable_xttrade_query: bool = False
    trade_accounts: str = ""
    trade_account_type: str = "STOCK"
    # 012 optional PostgreSQL persistence (off unless QMT_DB_URL is set).
    db_url: str = ""
    db_marketdata: bool = True
    db_pool_max: int = 5
    # 013 quote subscriptions/cache (read-only, disabled only with xtdata off).
    quote_subscription_store: str = "/broker/cache/quote-subscriptions-v1.json"
    quote_cache_max_age_ms: int = 10_000
    quote_subscription_max_codes: int = 100
    quote_subscription_max_official: int = 50
    quote_subscription_min_fallback_interval_s: int = 5
    # 014 derived portfolio analysis (registered only when xttrade query is enabled).
    enable_portfolio_analysis: bool = True
    # 017 local QMT custom-sector mutation. Disabled by default.
    enable_xtdata_sector_write: bool = False
    xtdata_sector_write_prefixes: str = "MCP/,AI/"
    # 018 formula/model execution. Disabled by default; names are server allowlisted.
    enable_formula_runtime: bool = False
    formula_allowlist: str = ""
    formula_output_sandbox: str = "/broker/formula-output"
    # MCP authorization discovery compatibility. The appliance remains a
    # resource server; token issuance is delegated to an external authorization server.
    public_base_url: str = ""
    oauth_authorization_servers: tuple[str, ...] = ()
    oauth_scopes_supported: tuple[str, ...] = DEFAULT_OAUTH_SCOPES
    oauth_resource: str = ""
    oauth_resource_name: str = "QMT MCP"
    auth_mode: str = "static"
    oauth_issuer: str = ""
    oauth_jwks_url: str = ""
    oauth_algorithms: tuple[str, ...] = ("RS256", "ES256")
    oauth_clock_skew_s: int = 30
    oauth_jwks_ttl_s: int = 300
    oauth_http_timeout_s: float = 5.0
    oauth_jwks_max_bytes: int = 1_048_576
    # 020 startup-static MCP tool visibility.
    tool_profile: str = "full"
    tool_allowlist: tuple[str, ...] = ()
    tool_denylist: tuple[str, ...] = ()

    @property
    def db_enabled(self) -> bool:
        return bool(self.db_url.strip())

    @property
    def auth_required(self) -> bool:
        return self.auth_mode in {"oauth", "hybrid"} or bool(self.token)

    @property
    def oauth_enabled(self) -> bool:
        return bool(self.authorization_servers)

    @property
    def sdk_oauth_enabled(self) -> bool:
        return self.auth_mode in {"oauth", "hybrid"}

    @property
    def authorization_servers(self) -> tuple[str, ...]:
        if self.oauth_authorization_servers:
            return self.oauth_authorization_servers
        return (self.oauth_issuer,) if self.oauth_issuer else ()

    @property
    def oauth_issuer_url(self) -> str:
        if self.oauth_issuer:
            return self.oauth_issuer
        return self.oauth_authorization_servers[0] if len(self.oauth_authorization_servers) == 1 else ""

    @property
    def oauth_resource_url(self) -> str:
        if self.oauth_resource:
            return self.oauth_resource
        if self.public_base_url:
            return f"{self.public_base_url}/mcp"
        return ""

    @property
    def effective_task_store(self) -> str:
        if self.task_store.strip():
            return self.task_store.strip()
        return str(Path(self.audit_path).with_name("mcp-tasks-v1.sqlite3"))

    def validate_security(self) -> None:
        if self.transport not in {"streamable-http", "http", "sse"}:
            raise McpCoreError(
                "config",
                "invalid QMT_MCP_TRANSPORT",
                {"transport": self.transport, "allowed": ["streamable-http", "http", "sse"]},
            )
        if self.auth_mode not in VALID_AUTH_MODES:
            raise McpCoreError(
                "config",
                "invalid QMT_MCP_AUTH_MODE",
                {"auth_mode": self.auth_mode, "allowed": sorted(VALID_AUTH_MODES)},
            )
        if not 1 <= self.mcp_list_page_size <= 1000:
            raise McpCoreError(
                "config",
                "QMT_MCP_LIST_PAGE_SIZE must be between 1 and 1000",
                {"value": self.mcp_list_page_size},
            )
        if not 0 <= self.mcp_gzip_minimum_size <= 10 * 1024 * 1024:
            raise McpCoreError(
                "config",
                "QMT_MCP_GZIP_MIN_SIZE must be between 0 and 10485760",
                {"value": self.mcp_gzip_minimum_size},
            )
        if not 0 <= self.task_ttl_ms <= 365 * 24 * 60 * 60 * 1000:
            raise McpCoreError(
                "config",
                "QMT_MCP_TASK_TTL_MS must be between 0 and 31536000000",
                {"value": self.task_ttl_ms},
            )
        if not 100 <= self.task_poll_interval_ms <= 60_000:
            raise McpCoreError(
                "config",
                "QMT_MCP_TASK_POLL_INTERVAL_MS must be between 100 and 60000",
                {"value": self.task_poll_interval_ms},
            )
        if not 1 <= self.task_max_retained <= 100_000:
            raise McpCoreError(
                "config",
                "QMT_MCP_TASK_MAX_RETAINED must be between 1 and 100000",
                {"value": self.task_max_retained},
            )
        if len(self.effective_task_store) > 4096:
            raise McpCoreError("config", "QMT_MCP_TASK_STORE is too long")
        if len(self.task_tools) > 100 or any(
            not name.startswith("qmt_") or len(name) > 128 for name in self.task_tools
        ):
            raise McpCoreError(
                "config",
                "QMT_MCP_TASK_TOOLS must contain at most 100 bounded qmt_ tool names",
            )
        if (
            self.auth_mode == "static"
            and not self.token
            and not (_is_loopback(self.host) and self.allow_unauth_loopback)
        ):
            raise McpCoreError(
                "auth",
                "QMT_MCP_TOKEN is required when MCP is bound to a non-loopback host",
                {"host": self.host},
            )
        if self.auth_mode == "hybrid" and not self.token:
            raise McpCoreError("auth", "QMT_MCP_TOKEN is required in hybrid auth mode")
        if self.sdk_oauth_enabled:
            self._validate_oauth()
        try:
            from .tool_contracts import ToolVisibilityPolicy

            ToolVisibilityPolicy(self.tool_profile, self.tool_allowlist, self.tool_denylist)
        except ValueError as exc:
            raise McpCoreError("config", str(exc)) from exc

    def _validate_oauth(self) -> None:
        issuer = self.oauth_issuer_url
        resource = self.oauth_resource_url
        if not issuer or not self.oauth_jwks_url or not resource:
            raise McpCoreError(
                "auth",
                "OAuth mode requires issuer, JWKS URL, and resource/public base URL",
            )
        if len(self.authorization_servers) != 1 or self.authorization_servers[0] != issuer:
            raise McpCoreError(
                "auth",
                "OAuth JWT mode requires exactly one authorization server matching the issuer",
            )
        for label, value in (("issuer", issuer), ("JWKS URL", self.oauth_jwks_url), ("resource", resource)):
            if not _is_secure_url(value):
                raise McpCoreError("auth", f"OAuth {label} must use HTTPS (HTTP is allowed only on loopback)")
            parsed = urlparse(value)
            if parsed.username or parsed.password or parsed.fragment:
                raise McpCoreError("auth", f"OAuth {label} must not contain credentials or a fragment")
        issuer_parts = urlparse(issuer)
        if issuer_parts.query:
            raise McpCoreError("auth", "OAuth issuer must not contain a query string")
        if urlparse(resource).query:
            raise McpCoreError("auth", "OAuth resource must not contain a query string")
        algorithms = set(self.oauth_algorithms)
        if not algorithms or not algorithms <= SAFE_JWT_ALGORITHMS:
            raise McpCoreError(
                "auth",
                "OAuth JWT algorithms must be an allowlist of asymmetric RS/PS/ES algorithms",
                {"allowed": sorted(SAFE_JWT_ALGORITHMS)},
            )
        if "qmt:read" not in self.oauth_scopes_supported:
            raise McpCoreError("auth", "OAuth scopes must include qmt:read")
        unknown_scopes = set(self.oauth_scopes_supported) - set(DEFAULT_OAUTH_SCOPES)
        if unknown_scopes:
            raise McpCoreError(
                "auth",
                "OAuth scopes contain unsupported values",
                {"unsupported": sorted(unknown_scopes), "allowed": list(DEFAULT_OAUTH_SCOPES)},
            )


def load_config(mcp_env_path: Path = DEFAULT_MCP_ENV) -> CoreConfig:
    env = _merged_env(mcp_env_path)
    host = env.get("MCP_HOST", "0.0.0.0")
    cfg = CoreConfig(
        broker_id=env.get("QMT_BROKER_ID", "unknown"),
        broker_name=env.get("QMT_BROKER_NAME", ""),
        xtquant_dir_win=env.get("QMT_XTQUANT_DIR_WIN", ""),
        userdata_win=env.get("QMT_USERDATA_WIN", ""),
        mcp_mode=env.get("QMT_MCP_MODE", "readonly") or "readonly",
        token=env.get("QMT_MCP_TOKEN", "").strip(),
        host=host,
        port=int(env.get("MCP_PORT", "8765")),
        transport=env.get("QMT_MCP_TRANSPORT", "streamable-http") or "streamable-http",
        audit_path=env.get("QMT_MCP_AUDIT_PATH", "/broker/logs/mcp-audit.jsonl"),
        worker_limit=max(1, int(env.get("QMT_MCP_WORKERS", "4"))),
        allow_unauth_loopback=env.get("QMT_MCP_ALLOW_UNAUTH_LOOPBACK", "0") == "1",
        enable_xtdata=env.get("QMT_MCP_ENABLE_XTDATA", "1") != "0",
        test_mode=env.get("QMT_MCP_TEST_MODE", "0") == "1",
        mcp_list_page_size=int(env.get("QMT_MCP_LIST_PAGE_SIZE", "50")),
        mcp_gzip_minimum_size=int(env.get("QMT_MCP_GZIP_MIN_SIZE", "1024")),
        tasks_enabled=env.get("QMT_MCP_TASKS_ENABLED", "1") != "0",
        task_store=env.get("QMT_MCP_TASK_STORE", "/broker/cache/mcp-tasks-v1.sqlite3"),
        task_ttl_ms=int(env.get("QMT_MCP_TASK_TTL_MS", "86400000")),
        task_poll_interval_ms=int(env.get("QMT_MCP_TASK_POLL_INTERVAL_MS", "1000")),
        task_max_retained=int(env.get("QMT_MCP_TASK_MAX_RETAINED", "1000")),
        task_tools=_split_csv(env.get("QMT_MCP_TASK_TOOLS", ",".join(DEFAULT_TASK_TOOLS))) or DEFAULT_TASK_TOOLS,
        task_conformance_fixtures=env.get("QMT_MCP_TASK_CONFORMANCE_FIXTURES", "0") == "1",
        readiness_poll_s=max(1.0, float(env.get("QMT_READINESS_POLL_S", "5"))),
        enable_connector=env.get("QMT_ENABLE_CONNECTOR", "0") == "1",
        connect_retry=max(1, int(env.get("QMT_CONNECT_RETRY", "8"))),
        connect_backoff_max_s=max(1.0, float(env.get("QMT_CONNECT_BACKOFF_MAX_S", "60"))),
        enable_xttrade_query=env.get("QMT_ENABLE_XTTRADE_QUERY", "0") == "1",
        trade_accounts=env.get("QMT_TRADE_ACCOUNTS", ""),
        trade_account_type=env.get("QMT_TRADE_ACCOUNT_TYPE", "STOCK") or "STOCK",
        db_url=env.get("QMT_DB_URL", ""),
        db_marketdata=env.get("QMT_DB_MARKETDATA", "1") != "0",
        db_pool_max=max(1, int(env.get("QMT_DB_POOL_MAX", "5"))),
        quote_subscription_store=env.get("QMT_QUOTE_SUBSCRIPTION_STORE", "/broker/cache/quote-subscriptions-v1.json"),
        quote_cache_max_age_ms=max(1, int(env.get("QMT_QUOTE_CACHE_MAX_AGE_MS", "10000"))),
        quote_subscription_max_codes=max(1, int(env.get("QMT_QUOTE_SUBSCRIPTION_MAX_CODES", "100"))),
        quote_subscription_max_official=max(1, int(env.get("QMT_QUOTE_SUBSCRIPTION_MAX_OFFICIAL", "50"))),
        quote_subscription_min_fallback_interval_s=max(
            1, int(env.get("QMT_QUOTE_SUBSCRIPTION_MIN_FALLBACK_INTERVAL_S", "5"))
        ),
        enable_portfolio_analysis=env.get("QMT_ENABLE_PORTFOLIO_ANALYSIS", "1") != "0",
        enable_xtdata_sector_write=env.get("QMT_ENABLE_XTDATA_SECTOR_WRITE", "0") == "1",
        xtdata_sector_write_prefixes=env.get("QMT_XTDATA_SECTOR_WRITE_PREFIXES", "MCP/,AI/") or "MCP/,AI/",
        enable_formula_runtime=env.get("QMT_ENABLE_FORMULA_RUNTIME", "0") == "1",
        formula_allowlist=env.get("QMT_FORMULA_ALLOWLIST", ""),
        formula_output_sandbox=env.get("QMT_FORMULA_OUTPUT_SANDBOX", "/broker/formula-output")
        or "/broker/formula-output",
        auth_mode=(env.get("QMT_MCP_AUTH_MODE", "static") or "static").strip().lower(),
        public_base_url=env.get("QMT_MCP_PUBLIC_BASE_URL", "").rstrip("/"),
        oauth_authorization_servers=_split_csv(env.get("QMT_MCP_OAUTH_AUTHORIZATION_SERVERS", "")),
        oauth_scopes_supported=_split_scopes(env.get("QMT_MCP_OAUTH_SCOPES", " ".join(DEFAULT_OAUTH_SCOPES)))
        or DEFAULT_OAUTH_SCOPES,
        oauth_resource=env.get("QMT_MCP_OAUTH_RESOURCE", "").rstrip("/"),
        oauth_resource_name=env.get("QMT_MCP_OAUTH_RESOURCE_NAME", "QMT MCP") or "QMT MCP",
        # The issuer is an exact security identifier. Do not normalize a
        # provider-owned trailing slash because JWT `iss` matching is literal.
        oauth_issuer=env.get("QMT_MCP_OAUTH_ISSUER", ""),
        oauth_jwks_url=env.get("QMT_MCP_OAUTH_JWKS_URL", ""),
        oauth_algorithms=_split_scopes(env.get("QMT_MCP_OAUTH_ALGORITHMS", "RS256 ES256")) or ("RS256", "ES256"),
        oauth_clock_skew_s=max(0, int(env.get("QMT_MCP_OAUTH_CLOCK_SKEW_S", "30"))),
        oauth_jwks_ttl_s=max(30, int(env.get("QMT_MCP_OAUTH_JWKS_TTL_S", "300"))),
        oauth_http_timeout_s=max(0.1, float(env.get("QMT_MCP_OAUTH_HTTP_TIMEOUT_S", "5"))),
        oauth_jwks_max_bytes=max(1024, int(env.get("QMT_MCP_OAUTH_JWKS_MAX_BYTES", "1048576"))),
        tool_profile=(env.get("QMT_MCP_TOOL_PROFILE", "full") or "full").strip().lower(),
        tool_allowlist=_split_csv(env.get("QMT_MCP_TOOL_ALLOWLIST", "")),
        tool_denylist=_split_csv(env.get("QMT_MCP_TOOL_DENYLIST", "")),
    )
    cfg.validate_security()
    return cfg
