"""Integration tier: app assembly + ASGI auth path.

Requires `fastmcp` installed; uses a fake `xtquant` so no Wine/broker pack is
needed. Skipped automatically in the unit tier (when fastmcp is absent).
"""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("fastmcp")

pytestmark = pytest.mark.integration

from qmt_mcp_core.app import create_app  # noqa: E402
from qmt_mcp_core.config import CoreConfig  # noqa: E402


def _config(tmp_path, token: str, **overrides) -> CoreConfig:
    values = dict(
        broker_id="acme",
        broker_name="ACME",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token=token,
        host="0.0.0.0",
        port=8765,
        transport="streamable-http",
        audit_path=str(tmp_path / "audit.jsonl"),
        worker_limit=2,
        allow_unauth_loopback=False,
        enable_xtdata=True,
        test_mode=True,
    )
    values.update(overrides)
    return CoreConfig(
        **values,
    )


def _drive_full(app, scope) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Run an ASGI request through the app, returning (status, headers, body)."""
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    status = start["status"]
    headers = start.get("headers", [])
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, headers, body


def _drive(app, scope) -> tuple[int, bytes]:
    """Run an ASGI request through the app, returning (status, body)."""
    status, _headers, body = _drive_full(app, scope)
    return status, body


def _scope(path: str, token: str | None = None) -> dict:
    headers = [(b"host", b"mcp.example.test")]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return {"type": "http", "path": path, "headers": headers, "method": "GET"}


def test_healthz_requires_token(fake_xtquant, tmp_path):
    app, _cfg, _health, _reg = create_app(_config(tmp_path, "s3cret"))
    status, _ = _drive(app, _scope("/healthz"))
    assert status == 401


def test_healthz_with_token_returns_health(fake_xtquant, tmp_path):
    app, _cfg, health, _reg = create_app(_config(tmp_path, "s3cret"))
    status, body = _drive(app, _scope("/healthz", token="s3cret"))
    assert status == 200
    doc = json.loads(body)
    assert doc["server"] == "live"
    assert "tool_families" in doc


def test_no_write_tools_registered(fake_xtquant, tmp_path):
    _app, _cfg, _health, registry = create_app(_config(tmp_path, "s3cret"))
    registry.assert_no_write_tools()  # must not raise


def test_livez_unauthenticated_and_minimal(fake_xtquant, tmp_path):
    app, _cfg, _health, _reg = create_app(_config(tmp_path, "s3cret"))
    # No token, yet /livez must answer 200 with only {ok, server}.
    status, body = _drive(app, _scope("/livez"))
    assert status == 200
    assert json.loads(body) == {"ok": True, "server": "live"}


def test_healthz_has_readiness_object(fake_xtquant, tmp_path):
    app, _cfg, _health, _reg = create_app(_config(tmp_path, "s3cret"))
    _status, body = _drive(app, _scope("/healthz", token="s3cret"))
    assert "readiness" in json.loads(body)


def test_oauth_resource_metadata_and_challenge(fake_xtquant, tmp_path):
    cfg = _config(
        tmp_path,
        "s3cret",
        public_base_url="https://qmt.example.com",
        oauth_authorization_servers=("https://auth.example.com",),
        oauth_scopes_supported=("qmt:read", "qmt:account"),
    )
    app, _cfg, _health, _reg = create_app(cfg)

    status, body = _drive(app, _scope("/.well-known/oauth-protected-resource"))
    assert status == 200
    doc = json.loads(body)
    assert doc["resource"] == "https://qmt.example.com/mcp"
    assert doc["authorization_servers"] == ["https://auth.example.com"]
    assert doc["scopes_supported"] == ["qmt:read", "qmt:account"]
    assert doc["bearer_methods_supported"] == ["header"]

    status, headers, _body = _drive_full(app, _scope("/healthz"))
    assert status == 401
    header_map = {k.lower(): v for k, v in headers}
    challenge = header_map[b"www-authenticate"].decode()
    assert 'resource_metadata="https://qmt.example.com/.well-known/oauth-protected-resource"' in challenge
    assert 'scope="qmt:read qmt:account"' in challenge
