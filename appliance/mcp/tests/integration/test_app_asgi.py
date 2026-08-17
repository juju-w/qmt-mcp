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

from qmt_mcp_apps.kline import KLINE_RESOURCE_URI, KLINE_TOOL_NAME  # noqa: E402
from qmt_mcp_core.app import NegotiatedGZipMiddleware, _accepts_gzip, create_app  # noqa: E402
from qmt_mcp_core.config import CoreConfig  # noqa: E402

APPS_EXTENSION_ID = "io.modelcontextprotocol/ui"
APPS_MIME_TYPE = "text/html;profile=mcp-app"

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


def _apps_request(method: str, request_id: int, params: dict | None = None) -> tuple[dict, dict]:
    payload, headers = _modern_request(method, request_id, params)
    payload["params"]["_meta"] = {
        **MODERN_META,
        "io.modelcontextprotocol/clientCapabilities": {
            "extensions": {APPS_EXTENSION_ID: {"mimeTypes": [APPS_MIME_TYPE]}}
        },
    }
    return payload, headers


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
    assert APPS_EXTENSION_ID not in result["capabilities"].get("extensions", {})
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"


def test_modern_tool_contracts_and_structured_results(fake_xtquant, tmp_path):
    app, _cfg, _health, registry = create_app(
        _config(
            tmp_path,
            "",
            host="127.0.0.1",
            allow_unauth_loopback=True,
            enable_xtdata=True,
            mcp_list_page_size=1000,
        )
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
        listed_result = _response_json(listed)["result"]
        tools = list(listed_result["tools"])
        cursor = listed_result.get("nextCursor")
        page = 1
        while cursor:
            next_payload, next_headers = _modern_request("tools/list", 100 + page, {"cursor": cursor})
            next_result = _response_json(client.post("/mcp", json=next_payload, headers=next_headers))["result"]
            tools.extend(next_result["tools"])
            cursor = next_result.get("nextCursor")
            page += 1

    assert listed.status_code == 200
    assert tools
    assert registry.tool_names() == registry.tool_names(visible_only=False)
    for tool in tools:
        _assert_complete_tool_contract(tool)
    by_name = {tool["name"]: tool for tool in tools}
    assert by_name["qmt_health"]["annotations"]["openWorldHint"] is False
    assert by_name["qmt_xtdata_snapshot"]["annotations"]["readOnlyHint"] is True
    assert by_name["qmt_xtdata_download_history"]["annotations"]["readOnlyHint"] is False
    assert by_name["qmt_factor_catalog"]["annotations"]["readOnlyHint"] is True
    assert "qmt_screen_instruments" in by_name, {
        "registered": registry.tool_names(),
        "listed": sorted(by_name),
        "mcp_callable": registry._tools["qmt_screen_instruments"]["mcp_callable"] is not None,
    }
    screen_tool = by_name["qmt_screen_instruments"]
    assert "_meta" not in screen_tool
    universe_schema = screen_tool["inputSchema"]["properties"]["universe"]
    universe_definition = screen_tool["inputSchema"]["$defs"][universe_schema["$ref"].rsplit("/", 1)[-1]]
    assert set(universe_definition["properties"]) >= {"kind", "values", "policy", "include_suspended"}
    assert registry.required_scopes("qmt_screen_instruments") == ("qmt:read", "qmt:market")
    assert "qmt_screen_instruments" in _cfg.task_tools

    assert success.status_code == 200
    success_result = _response_json(success)["result"]
    _assert_equivalent_result(success_result, ok=True)
    assert success_result["structuredContent"]["tool_visibility"]["profile"] == "full"

    assert refused.status_code == 200
    error_result = _response_json(refused)["result"]
    _assert_equivalent_result(error_result, ok=False)
    assert error_result["structuredContent"]["error_type"] == "validation"


def test_kline_app_discovery_resource_and_text_fallback(fake_xtquant, tmp_path):
    times = ["20260813", "20260814"]
    values = {
        "open": [130.0, 134.8],
        "high": [136.0, 136.8],
        "low": [129.0, 133.9],
        "close": [135.0, 136.42],
        "volume": [100_000, 120_000],
        "amount": [13_500_000, 16_370_400],
    }

    def market_data(*_args):
        return {
            "688234.SH": {
                field: {time: field_values[index] for index, time in enumerate(times)}
                for field, field_values in values.items()
            }
        }

    fake_xtquant.get_market_data_ex = market_data
    fake_xtquant.get_instrument_detail = lambda *_args: {"InstrumentName": "天岳先进"}
    app, _cfg, _health, registry = create_app(
        _config(tmp_path, "", host="127.0.0.1", allow_unauth_loopback=True, enable_xtdata=True)
    )
    discover_payload, discover_headers = _apps_request("server/discover", 50)
    list_payload, list_headers = _apps_request("tools/list", 51)
    resource_payload, resource_headers = _apps_request("resources/read", 52, {"uri": KLINE_RESOURCE_URI})
    resource_headers["mcp-name"] = KLINE_RESOURCE_URI
    call_payload, call_headers = _apps_request(
        "tools/call",
        53,
        {
            "name": KLINE_TOOL_NAME,
            "arguments": {"code": "688234.SH", "period": "1d", "count": 120, "dividend_type": "front"},
        },
    )

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        discovered = client.post("/mcp", json=discover_payload, headers=discover_headers)
        listed = client.post("/mcp", json=list_payload, headers=list_headers)
        resource = client.post("/mcp", json=resource_payload, headers=resource_headers)
        called = client.post("/mcp", json=call_payload, headers=call_headers)

    capabilities = _response_json(discovered)["result"]["capabilities"]
    assert capabilities["extensions"][APPS_EXTENSION_ID] == {}

    tools = {tool["name"]: tool for tool in _response_json(listed)["result"]["tools"]}
    chart_tool = tools[KLINE_TOOL_NAME]
    assert chart_tool["_meta"]["ui"] == {
        "resourceUri": KLINE_RESOURCE_URI,
        "visibility": ["model", "app"],
    }
    assert chart_tool["annotations"]["readOnlyHint"] is True
    assert "resolve_instrument" in chart_tool["description"]
    assert "qmt_xtdata_bars" in chart_tool["description"]

    contents = _response_json(resource)["result"]["contents"]
    assert len(contents) == 1
    assert contents[0]["uri"] == KLINE_RESOURCE_URI
    assert contents[0]["mimeType"] == APPS_MIME_TYPE
    assert "@modelcontextprotocol/ext-apps" not in contents[0]["text"]
    assert "QMT K-Line" in contents[0]["text"]
    assert len(contents[0]["text"].encode()) < 1_048_576

    result = _response_json(called)["result"]
    structured = result["structuredContent"]
    assert result["isError"] is False
    assert structured["instrument"] == {"code": "688234.SH", "name": "天岳先进"}
    assert structured["range"] == {"start": "20260813", "end": "20260814", "bar_count": 2}
    assert round(structured["summary"]["change"], 2) == 1.42
    assert result["content"][0]["text"].startswith("天岳先进 (688234.SH) 1d K-line")
    assert not result["content"][0]["text"].startswith("{")
    assert registry.required_scopes(KLINE_TOOL_NAME) == ("qmt:read", "qmt:market")

    raw = registry._tools["qmt_xtdata_bars"]["callable"](
        codes=["688234.SH"],
        period="1d",
        fields=list(values),
        count=120,
        dividend_type="front",
    )
    assert [row["time"] for row in raw["rows"]] == [bar["time"] for bar in structured["bars"]]
    assert [row["close"] for row in raw["rows"]] == [bar["close"] for bar in structured["bars"]]


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
    assert app.apps_extension is None
    assert registry.visibility_summary()["hidden_count"] > 0
    hidden_doc = _response_json(hidden_call)
    assert hidden_doc.get("error") or hidden_doc["result"]["isError"] is True


@pytest.mark.parametrize(
    ("headers", "payload", "expected_id", "requested"),
    [
        (
            {"accept": "application/json, text/event-stream"},
            {
                "jsonrpc": "2.0",
                "id": 41,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "legacy-test", "version": "1.0.0"},
                },
            },
            41,
            "",
        ),
        (
            {
                "accept": "application/json, text/event-stream",
                "mcp-protocol-version": "2025-11-25",
            },
            {"jsonrpc": "2.0", "id": "old", "method": "tools/list", "params": {}},
            "old",
            "2025-11-25",
        ),
        (
            {
                "accept": "application/json, text/event-stream",
                "mcp-protocol-version": "2099-01-01",
            },
            {"jsonrpc": "2.0", "id": 43, "method": "server/discover", "params": {}},
            43,
            "2099-01-01",
        ),
    ],
)
def test_non_modern_protocol_requests_are_rejected_without_session(
    fake_xtquant, tmp_path, headers, payload, expected_id, requested
):
    app, _cfg, _health, _reg = create_app(
        _config(
            tmp_path,
            "",
            host="127.0.0.1",
            allow_unauth_loopback=True,
            enable_xtdata=False,
        )
    )

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        response = client.post("/mcp", json=payload, headers=headers)

    assert response.status_code == 400
    assert "mcp-session-id" not in response.headers
    document = response.json()
    assert document["id"] == expected_id
    assert document["error"] == {
        "code": -32022,
        "message": "Unsupported MCP protocol version",
        "data": {"supported": [MODERN_VERSION], "requested": requested},
    }


def test_malformed_legacy_request_is_bounded_and_has_null_id(fake_xtquant, tmp_path):
    app, _cfg, _health, _reg = create_app(
        _config(tmp_path, "", host="127.0.0.1", allow_unauth_loopback=True, enable_xtdata=False)
    )

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        response = client.post(
            "/mcp",
            content=b'{"jsonrpc":"2.0","id":',
            headers={"mcp-protocol-version": "2025-11-25"},
        )

    assert response.status_code == 400
    assert response.json()["id"] is None
    assert response.json()["error"]["code"] == -32022
    assert "mcp-session-id" not in response.headers


def test_oversized_legacy_request_is_rejected_without_buffering_an_id(fake_xtquant, tmp_path):
    app, _cfg, _health, _reg = create_app(
        _config(tmp_path, "", host="127.0.0.1", allow_unauth_loopback=True, enable_xtdata=False)
    )

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        response = client.post(
            "/mcp",
            content=b"x" * (1_048_576 + 1),
            headers={"mcp-protocol-version": "2025-11-25"},
        )

    assert response.status_code == 400
    assert response.json()["id"] is None
    assert response.json()["error"]["code"] == -32022


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_standalone_session_methods_are_not_supported(fake_xtquant, tmp_path, method):
    app, _cfg, _health, _reg = create_app(
        _config(tmp_path, "", host="127.0.0.1", allow_unauth_loopback=True, enable_xtdata=False)
    )

    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        response = client.request(method, "/mcp", headers={"mcp-protocol-version": MODERN_VERSION})

    assert response.status_code == 405
    assert response.json()["error"]["code"] == -32600
    assert "mcp-session-id" not in response.headers
