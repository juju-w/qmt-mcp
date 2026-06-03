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


def test_invalid_transport_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("QMT_MCP_TOKEN", "s3cret")
    monkeypatch.setenv("QMT_MCP_TRANSPORT", "carrier-pigeon")
    with pytest.raises(McpCoreError) as exc:
        load_config(_empty_env(tmp_path))
    assert exc.value.error_type == "config"


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
