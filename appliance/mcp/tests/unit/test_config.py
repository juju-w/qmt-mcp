"""Unit tests for config parsing and fail-closed security validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from qmt_mcp_core.config import load_config
from qmt_mcp_core.errors import McpCoreError


def _empty_env(tmp_path: Path) -> Path:
    return tmp_path / "missing-mcp.env"


def test_token_required_on_non_loopback(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert exc.value.error_type == "auth"


def test_loopback_without_token_allowed_when_opted_in(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("QMT_MCP_ALLOW_UNAUTH_LOOPBACK", "1")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.auth_required is False
    assert cfg.host == "127.0.0.1"


def test_token_present_enables_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.auth_required is True
    assert cfg.token == "s3cret"


def test_static_auth_mode_is_backward_compatible_default(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.auth_mode == "static"
    assert cfg.auth_required is True
    assert cfg.sdk_oauth_enabled is False


def test_invalid_transport_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_TRANSPORT", "carrier-pigeon")
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert exc.value.error_type == "config"


def test_legacy_sse_transport_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_TRANSPORT", "sse")
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert exc.value.error_type == "config"
    assert exc.value.details["allowed"] == ["streamable-http", "http"]


def test_http_transport_alias_remains_available(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_TRANSPORT", "http")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.transport == "http"


def test_defaults_and_env_file_overlay(monkeypatch, tmp_path):
    env_file = tmp_path / "mcp.env"
    env_file.write_text(
        "QMT_MCP_TOKEN='from-file'\nQMT_BROKER_ID='acme'\nMCP_PORT='9000'\n",
        encoding="utf-8",
    )
    cfg = load_config(env_file)
    assert cfg.broker_id == "acme"
    assert cfg.token == "from-file"
    assert cfg.port == 9000
    # unset knobs fall back to declared defaults
    assert cfg.transport == "streamable-http"
    assert cfg.worker_limit >= 1
    assert cfg.enable_xtdata is True
    assert cfg.mcp_list_page_size == 50
    assert cfg.mcp_gzip_minimum_size == 1024
    assert cfg.tasks_enabled is True
    assert cfg.task_ttl_ms == 86_400_000
    assert cfg.task_poll_interval_ms == 1000
    assert cfg.task_max_retained == 1000


def test_process_env_overrides_file(monkeypatch, tmp_path):
    env_file = tmp_path / "mcp.env"
    env_file.write_text("QMT_MCP_TOKEN='from-file'\n", encoding="utf-8")
    monkeypatch.setenv("QMT_MCP_TOKEN", "from-process")
    cfg = load_config(env_file)
    assert cfg.token == "from-process"


def test_readiness_connector_knob_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.readiness_poll_s == 5.0
    assert cfg.enable_connector is False  # fail-closed: connector off by default
    assert cfg.connect_retry == 8
    assert cfg.connect_backoff_max_s == 60.0


def test_connector_knobs_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_ENABLE_CONNECTOR", "1")
    monkeypatch.setenv("QMT_READINESS_POLL_S", "2")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.enable_connector is True
    assert cfg.readiness_poll_s == 2.0


def test_oauth_discovery_knobs_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_PUBLIC_BASE_URL", "https://qmt.example.com/")
    monkeypatch.setenv("QMT_MCP_OAUTH_AUTHORIZATION_SERVERS", "https://auth1.example.com, https://auth2.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_SCOPES", "qmt:read qmt:account")
    monkeypatch.setenv("QMT_MCP_OAUTH_RESOURCE", "https://qmt.example.com/mcp/")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.public_base_url == "https://qmt.example.com"
    assert cfg.oauth_enabled is True
    assert cfg.oauth_authorization_servers == ("https://auth1.example.com", "https://auth2.example.com")
    assert cfg.oauth_scopes_supported == ("qmt:read", "qmt:account")
    assert cfg.oauth_resource == "https://qmt.example.com/mcp"


def test_oauth_mode_loads_complete_resource_server_config(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("QMT_MCP_AUTH_MODE", "oauth")
    monkeypatch.setenv("QMT_MCP_PUBLIC_BASE_URL", "https://qmt.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_AUTHORIZATION_SERVERS", "https://auth.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_JWKS_URL", "https://auth.example.com/jwks.json")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.auth_required is True
    assert cfg.sdk_oauth_enabled is True
    assert cfg.oauth_resource_url == "https://qmt.example.com/mcp"
    assert cfg.oauth_issuer_url == "https://auth.example.com"
    assert cfg.oauth_scopes_supported == (
        "qmt:read",
        "qmt:market",
        "qmt:account",
        "qmt:manage",
        "qmt:admin",
    )


def test_oauth_issuer_preserves_provider_trailing_slash(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("QMT_MCP_AUTH_MODE", "oauth")
    monkeypatch.setenv("QMT_MCP_PUBLIC_BASE_URL", "https://qmt.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_ISSUER", "https://auth.example.com/")
    monkeypatch.setenv("QMT_MCP_OAUTH_JWKS_URL", "https://auth.example.com/jwks.json")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.oauth_issuer_url == "https://auth.example.com/"
    assert cfg.authorization_servers == ("https://auth.example.com/",)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("QMT_MCP_OAUTH_JWKS_URL", ""),
        ("QMT_MCP_OAUTH_JWKS_URL", "http://auth.example.com/jwks.json"),
        ("QMT_MCP_OAUTH_ALGORITHMS", "HS256"),
        ("QMT_MCP_OAUTH_RESOURCE", "https://qmt.example.com/mcp?tenant=unsafe"),
    ],
)
def test_oauth_mode_rejects_incomplete_or_unsafe_config(monkeypatch, tmp_path, name, value):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("QMT_MCP_AUTH_MODE", "oauth")
    monkeypatch.setenv("QMT_MCP_PUBLIC_BASE_URL", "https://qmt.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_AUTHORIZATION_SERVERS", "https://auth.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_JWKS_URL", "https://auth.example.com/jwks.json")
    monkeypatch.setenv(name, value)
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert exc.value.error_type == "auth"


def test_hybrid_mode_requires_static_token(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("QMT_MCP_AUTH_MODE", "hybrid")
    monkeypatch.setenv("QMT_MCP_PUBLIC_BASE_URL", "https://qmt.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_AUTHORIZATION_SERVERS", "https://auth.example.com")
    monkeypatch.setenv("QMT_MCP_OAUTH_JWKS_URL", "https://auth.example.com/jwks.json")
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert "hybrid" in exc.value.message


def test_tool_profile_knobs_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_TOOL_PROFILE", "CUSTOM")
    monkeypatch.setenv("QMT_MCP_TOOL_ALLOWLIST", "qmt_xtdata_snapshot,qmt_xtdata_option_*")
    monkeypatch.setenv("QMT_MCP_TOOL_DENYLIST", "qmt_xtdata_option_quotes")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.tool_profile == "custom"
    assert cfg.tool_allowlist == ("qmt_xtdata_snapshot", "qmt_xtdata_option_*")
    assert cfg.tool_denylist == ("qmt_xtdata_option_quotes",)


def test_pagination_and_compression_knobs_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_LIST_PAGE_SIZE", "17")
    monkeypatch.setenv("QMT_MCP_GZIP_MIN_SIZE", "0")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.mcp_list_page_size == 17
    assert cfg.mcp_gzip_minimum_size == 0


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("QMT_MCP_LIST_PAGE_SIZE", "0"),
        ("QMT_MCP_LIST_PAGE_SIZE", "1001"),
        ("QMT_MCP_GZIP_MIN_SIZE", "-1"),
        ("QMT_MCP_GZIP_MIN_SIZE", "10485761"),
    ],
)
def test_invalid_pagination_or_compression_knobs_fail_closed(monkeypatch, tmp_path, name, value):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv(name, value)
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert exc.value.error_type == "config"


def test_task_knobs_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_TASKS_ENABLED", "0")
    monkeypatch.setenv("QMT_MCP_TASK_STORE", str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setenv("QMT_MCP_TASK_TTL_MS", "0")
    monkeypatch.setenv("QMT_MCP_TASK_POLL_INTERVAL_MS", "250")
    monkeypatch.setenv("QMT_MCP_TASK_MAX_RETAINED", "17")
    monkeypatch.setenv("QMT_MCP_TASK_TOOLS", "qmt_one,qmt_two")
    monkeypatch.setenv("QMT_MCP_TASK_CONFORMANCE_FIXTURES", "1")
    cfg = load_config(_empty_env(tmp_path))
    assert cfg.tasks_enabled is False
    assert cfg.effective_task_store == str(tmp_path / "tasks.sqlite3")
    assert cfg.task_ttl_ms == 0
    assert cfg.task_poll_interval_ms == 250
    assert cfg.task_max_retained == 17
    assert cfg.task_tools == ("qmt_one", "qmt_two")
    assert cfg.task_conformance_fixtures is True


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("QMT_MCP_TASK_TTL_MS", "-1"),
        ("QMT_MCP_TASK_TTL_MS", "31536000001"),
        ("QMT_MCP_TASK_POLL_INTERVAL_MS", "99"),
        ("QMT_MCP_TASK_POLL_INTERVAL_MS", "60001"),
        ("QMT_MCP_TASK_MAX_RETAINED", "0"),
        ("QMT_MCP_TASK_MAX_RETAINED", "100001"),
        ("QMT_MCP_TASK_TOOLS", "not-a-qmt-tool"),
    ],
)
def test_invalid_task_knobs_fail_closed(monkeypatch, tmp_path, name, value):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv(name, value)
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert exc.value.error_type == "config"


@pytest.mark.parametrize("profile", ["unknown", ""])
def test_invalid_or_empty_custom_tool_profile_fails_closed(monkeypatch, tmp_path, profile):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_TOOL_PROFILE", profile or "custom")
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert exc.value.error_type == "config"
