"""Integration tier: app assembly + ASGI auth path.

Requires the official `mcp` package; uses a fake `xtquant` so no Wine/broker
pack is needed. Skipped automatically in the unit tier (when mcp is absent).
"""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("mcp")

pytestmark = pytest.mark.integration

from starlette.testclient import TestClient  # noqa: E402

from qmt_mcp_core.app import NegotiatedGZipMiddleware, _accepts_gzip, create_app  # noqa: E402
from qmt_mcp_core.config import CoreConfig  # noqa: E402

MODERN_VERSION = "2026-07-28"
MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": MODERN_VERSION,
    "io.modelcontextprotocol/clientInfo": {"name": "integration-test", "version": "1.0.0"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


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


def _response_json(response) -> dict:
    if "text/event-stream" not in response.headers.get("content-type", ""):
        return response.json()
    for line in response.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())
    raise AssertionError("SSE response did not contain a data event")


def _modern_request(method: str, request_id: int, params: dict | None = None) -> tuple[dict, dict]:
    request_params = dict(params or {})
    request_params["_meta"] = MODERN_META
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": MODERN_VERSION,
        "mcp-method": method,
    }
    if method == "tools/call":
        headers["mcp-name"] = request_params["name"]
    return (
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": request_params},
        headers,
    )


def _assert_complete_tool_contract(tool: dict) -> None:
    assert tool["title"]
    assert tool["description"]
    assert tool["inputSchema"]["type"] == "object"
    assert tool["outputSchema"]["type"] == "object"
    assert "ok" in tool["outputSchema"]["required"]
    assert tool["outputSchema"]["properties"]["ok"]["type"] == "boolean"
    assert tool["outputSchema"]["additionalProperties"] is True
    assert set(tool["annotations"]) >= {
        "readOnlyHint",
        "destructiveHint",
        "idempotentHint",
        "openWorldHint",
    }


def _assert_equivalent_result(result: dict, *, ok: bool) -> None:
    assert result["structuredContent"]["ok"] is ok
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert result["isError"] is (not ok)


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
    assert 'resource_metadata="https://qmt.example.com/.well-known/oauth-protected-resource/mcp"' in challenge
    assert 'scope="qmt:read"' in challenge
    assert 'resource="https://qmt.example.com/mcp"' in challenge


def test_modern_discover_is_stateless_and_cache_hinted(fake_xtquant, tmp_path):
    app, _cfg, _health, _reg = create_app(
        _config(tmp_path, "", host="127.0.0.1", allow_unauth_loopback=True, enable_xtdata=False)
    )
    request_meta = MODERN_META
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": "server/discover",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "server/discover",
        "params": {"_meta": request_meta},
    }

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        response = client.post("/mcp", json=payload, headers=headers)

    assert response.status_code == 200
    assert "mcp-session-id" not in response.headers
    result = _response_json(response)["result"]
    assert result["supportedVersions"] == ["2026-07-28"]
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"


def test_modern_tool_contracts_and_structured_results(fake_xtquant, tmp_path):
    app, _cfg, _health, registry = create_app(
        _config(tmp_path, "", host="127.0.0.1", allow_unauth_loopback=True, enable_xtdata=True)
    )
    list_payload, list_headers = _modern_request("tools/list", 10)
    success_payload, success_headers = _modern_request(
        "tools/call",
        11,
        {"name": "qmt_capabilities", "arguments": {}},
    )
    error_payload, error_headers = _modern_request(
        "tools/call",
        12,
        {"name": "qmt_xtdata_snapshot", "arguments": {"codes": []}},
    )

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        listed = client.post("/mcp", json=list_payload, headers=list_headers)
        success = client.post("/mcp", json=success_payload, headers=success_headers)
        refused = client.post("/mcp", json=error_payload, headers=error_headers)

    assert listed.status_code == 200
    tools = _response_json(listed)["result"]["tools"]
    assert tools
    assert registry.tool_names() == registry.tool_names(visible_only=False)
    for tool in tools:
        _assert_complete_tool_contract(tool)
    by_name = {tool["name"]: tool for tool in tools}
    assert by_name["qmt_health"]["annotations"]["openWorldHint"] is False
    assert by_name["qmt_xtdata_snapshot"]["annotations"]["readOnlyHint"] is True
    assert by_name["qmt_xtdata_download_history"]["annotations"]["readOnlyHint"] is False

    assert success.status_code == 200
    success_result = _response_json(success)["result"]
    _assert_equivalent_result(success_result, ok=True)
    assert success_result["structuredContent"]["tool_visibility"]["profile"] == "full"

    assert refused.status_code == 200
    error_result = _response_json(refused)["result"]
    _assert_equivalent_result(error_result, ok=False)
    assert error_result["structuredContent"]["error_type"] == "validation"


def test_modern_tools_list_uses_stable_cursor_pages_and_rejects_invalid_cursor(fake_xtquant, tmp_path):
    app, _cfg, _health, _registry = create_app(
        _config(
            tmp_path,
            "",
            host="127.0.0.1",
            allow_unauth_loopback=True,
            enable_xtdata=False,
            mcp_list_page_size=1,
        )
    )
    first_payload, first_headers = _modern_request("tools/list", 30)

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        first_response = client.post("/mcp", json=first_payload, headers=first_headers)
        first = _response_json(first_response)["result"]
        assert len(first["tools"]) == 1
        assert first["nextCursor"]
        assert first["ttlMs"] == 0
        assert first["cacheScope"] == "private"

        second_payload, second_headers = _modern_request(
            "tools/list",
            31,
            {"cursor": first["nextCursor"]},
        )
        second_response = client.post("/mcp", json=second_payload, headers=second_headers)
        second = _response_json(second_response)["result"]

        invalid_payload, invalid_headers = _modern_request(
            "tools/list",
            32,
            {"cursor": "not-a-valid-cursor"},
        )
        invalid_response = client.post("/mcp", json=invalid_payload, headers=invalid_headers)
        invalid = _response_json(invalid_response)

    assert len(second["tools"]) == 1
    assert "nextCursor" not in second
    assert [first["tools"][0]["name"], second["tools"][0]["name"]] == [
        "qmt_capabilities",
        "qmt_health",
    ]
    assert invalid["error"]["code"] == -32602
    assert invalid["error"]["message"] == "Invalid pagination cursor"
    assert "not-a-valid-cursor" not in invalid_response.text


def test_tools_list_gzip_is_negotiated_for_json_and_excluded_for_sse(fake_xtquant, tmp_path):
    app, _cfg, _health, _registry = create_app(
        _config(
            tmp_path,
            "",
            host="127.0.0.1",
            allow_unauth_loopback=True,
            enable_xtdata=True,
            mcp_list_page_size=1000,
            mcp_gzip_minimum_size=1,
        )
    )
    payload, headers = _modern_request("tools/list", 40)

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        identity = client.post("/mcp", json=payload, headers={**headers, "accept-encoding": "identity"})
        compressed = client.post("/mcp", json=payload, headers={**headers, "accept-encoding": "gzip"})
        rejected = client.post("/mcp", json=payload, headers={**headers, "accept-encoding": "gzip;q=0"})

    assert identity.status_code == 200
    assert compressed.status_code == 200
    assert compressed.headers["content-encoding"] == "gzip"
    assert "accept-encoding" in compressed.headers["vary"].lower()
    assert compressed.json() == identity.json()
    assert int(compressed.headers["content-length"]) < len(identity.content) * 0.6
    assert "content-encoding" not in rejected.headers
    assert rejected.json() == identity.json()

    async def sse_app(_scope, _receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        await send({"type": "http.response.body", "body": b"data: first\n\n", "more_body": True})
        await send({"type": "http.response.body", "body": b"data: second\n\n"})

    streamed = NegotiatedGZipMiddleware(sse_app, minimum_size=1)
    status, raw_headers, body = _drive_full(
        streamed,
        {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"accept-encoding", b"gzip")],
            "method": "POST",
        },
    )
    header_map = {key.lower(): value for key, value in raw_headers}
    assert status == 200
    assert header_map[b"content-type"] == b"text/event-stream"
    assert b"content-encoding" not in header_map
    assert body == b"data: first\n\ndata: second\n\n"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("gzip", True),
        ("br, gzip;q=0.5", True),
        ("gzip;q=0", False),
        ("br, *;q=0.2", True),
        ("identity", False),
        ("gzip;q=broken", False),
    ],
)
def test_gzip_accept_encoding_quality_negotiation(header, expected):
    assert _accepts_gzip(header) is expected


def test_core_profile_hides_and_rejects_non_core_tools(fake_xtquant, tmp_path):
    app, _cfg, _health, registry = create_app(
        _config(
            tmp_path,
            "",
            host="127.0.0.1",
            allow_unauth_loopback=True,
            enable_xtdata=True,
            tool_profile="core",
        )
    )
    list_payload, list_headers = _modern_request("tools/list", 20)
    call_payload, call_headers = _modern_request(
        "tools/call",
        21,
        {"name": "qmt_xtdata_snapshot", "arguments": {"codes": ["510300.SH"]}},
    )

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        listed = client.post("/mcp", json=list_payload, headers=list_headers)
        hidden_call = client.post("/mcp", json=call_payload, headers=call_headers)

    names = {tool["name"] for tool in _response_json(listed)["result"]["tools"]}
    assert names == {"qmt_health", "qmt_capabilities"}
    assert registry.visibility_summary()["hidden_count"] > 0
    hidden_doc = _response_json(hidden_call)
    assert hidden_doc.get("error") or hidden_doc["result"]["isError"] is True


def test_legacy_initialize_and_session_share_modern_endpoint(fake_xtquant, tmp_path):
    app, _cfg, _health, _reg = create_app(
        _config(
            tmp_path,
            "",
            host="127.0.0.1",
            allow_unauth_loopback=True,
            enable_xtdata=False,
            mcp_list_page_size=1,
        )
    )
    accept = {"accept": "application/json, text/event-stream"}
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "legacy-integration-test", "version": "1.0.0"},
        },
    }

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        response = client.post("/mcp", json=initialize, headers=accept)
        assert response.status_code == 200
        session_id = response.headers["mcp-session-id"]
        assert _response_json(response)["result"]["protocolVersion"] == "2025-11-25"

        session_headers = {
            **accept,
            "mcp-session-id": session_id,
            "mcp-protocol-version": "2025-11-25",
        }
        initialized = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=session_headers,
        )
        assert initialized.status_code == 202

        listed = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=session_headers,
        )
        assert listed.status_code == 200
        first_page = _response_json(listed)["result"]
        assert len(first_page["tools"]) == 1
        assert first_page["nextCursor"]
        for tool in first_page["tools"]:
            _assert_complete_tool_contract(tool)

        listed_next = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/list",
                "params": {"cursor": first_page["nextCursor"]},
            },
            headers=session_headers,
        )
        assert listed_next.status_code == 200
        second_page = _response_json(listed_next)["result"]
        assert len(second_page["tools"]) == 1
        assert "nextCursor" not in second_page
        assert {first_page["tools"][0]["name"], second_page["tools"][0]["name"]} == {
            "qmt_health",
            "qmt_capabilities",
        }
        _assert_complete_tool_contract(second_page["tools"][0])

        called = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "qmt_capabilities", "arguments": {}},
            },
            headers=session_headers,
        )
        assert called.status_code == 200
        _assert_equivalent_result(_response_json(called)["result"], ok=True)
