"""OAuth JWT/JWKS and request-specific MCP tool authorization."""

from __future__ import annotations

import json
import time
from urllib.request import Request

import pytest

pytest.importorskip("mcp")

pytestmark = pytest.mark.integration

import anyio  # noqa: E402
import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from qmt_mcp_core import auth as auth_module  # noqa: E402
from qmt_mcp_core.app import create_app  # noqa: E402
from qmt_mcp_core.auth import JwksCache, JwtTokenVerifier  # noqa: E402
from qmt_mcp_core.config import CoreConfig  # noqa: E402

ISSUER = "https://auth.example.com"
RESOURCE = "https://qmt.example.com/mcp"
MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {"name": "oauth-test", "version": "1.0.0"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


def _config(tmp_path, **overrides) -> CoreConfig:
    values = dict(
        broker_id="acme",
        broker_name="ACME",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token="",
        host="0.0.0.0",
        port=8765,
        transport="streamable-http",
        audit_path=str(tmp_path / "audit.jsonl"),
        worker_limit=2,
        allow_unauth_loopback=False,
        enable_xtdata=True,
        test_mode=True,
        auth_mode="oauth",
        public_base_url="https://qmt.example.com",
        oauth_authorization_servers=(ISSUER,),
        oauth_scopes_supported=("qmt:read", "qmt:market", "qmt:account", "qmt:manage", "qmt:admin"),
        oauth_resource=RESOURCE,
        oauth_issuer=ISSUER,
        oauth_jwks_url=f"{ISSUER}/jwks.json",
        oauth_algorithms=("RS256",),
    )
    values.update(overrides)
    config = CoreConfig(**values)
    config.validate_security()
    return config


def _key(kid: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public_jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return private, public_jwk


def _token(private, kid: str, scopes: str, **claim_overrides) -> str:
    claims = {
        "iss": ISSUER,
        "aud": RESOURCE,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "client_id": "oauth-test-client",
        "sub": "operator-1",
        "scope": scopes,
    }
    claims.update(claim_overrides)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": kid})


class _Response:
    def __init__(self, document):
        self.body = json.dumps(document).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, limit):
        return self.body[:limit]

    def geturl(self):
        return ISSUER + "/jwks.json"


def _install_jwks(monkeypatch, document):
    monkeypatch.setattr(auth_module, "_open_jwks", lambda _request, timeout: _Response(document))


def _request(method: str, request_id: int, *, name: str | None = None):
    params = {"_meta": MODERN_META}
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": method,
    }
    if name is not None:
        params.update({"name": name, "arguments": {}})
        headers["mcp-name"] = name
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, headers


def _task_request(method: str, request_id: int, params: dict):
    body_params = {
        **params,
        "_meta": {
            **MODERN_META,
            "io.modelcontextprotocol/clientCapabilities": {"extensions": {"io.modelcontextprotocol/tasks": {}}},
        },
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": method,
    }
    if method == "tools/call":
        headers["mcp-name"] = body_params["name"]
    else:
        headers["mcp-name"] = body_params["taskId"]
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params}, headers


def _response_json(response):
    if "text/event-stream" not in response.headers.get("content-type", ""):
        return response.json()
    for line in response.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())
    raise AssertionError("missing SSE data event")


def test_jwt_verifier_validates_signature_issuer_audience_expiry_and_scope(tmp_path):
    private, public = _key("key-1")
    wrong_private, _wrong_public = _key("wrong-key")
    verifier = JwtTokenVerifier(_config(tmp_path), fetcher=lambda: {"keys": [public]})

    valid = anyio.run(verifier.verify_token, _token(private, "key-1", "qmt:read qmt:market"))
    assert valid is not None
    assert valid.client_id == "oauth-test-client"
    assert valid.subject == "operator-1"
    assert valid.scopes == ["qmt:market", "qmt:read"]
    assert valid.resource == RESOURCE

    audience_array = anyio.run(
        verifier.verify_token,
        _token(private, "key-1", "ignored", aud=[RESOURCE], scope=None, scp=["qmt:read"]),
    )
    assert audience_array is not None
    assert audience_array.scopes == ["qmt:read"]

    unsigned_claims = jwt.decode(valid.token, options={"verify_signature": False})
    invalid_tokens = [
        _token(wrong_private, "key-1", "qmt:read"),
        _token(private, "key-1", "qmt:read", iss="https://wrong.example.com"),
        _token(private, "key-1", "qmt:read", aud="https://wrong.example.com/mcp"),
        _token(private, "key-1", "qmt:read", exp=int(time.time()) - 120),
        _token(private, "key-1", "qmt:read", exp=None),
        _token(private, "key-1", "qmt:read", nbf=int(time.time()) + 120),
        _token(private, "unknown-key", "qmt:read"),
        _token(private, "key-1", "qmt:read", client_id=None, azp=None),
        _token(private, "key-1", "qmt:read", scp=["qmt:account"]),
        _token(private, "key-1", "ignored", scope=["qmt:read"]),
        _token(private, "key-1", "ignored", scope=None, scp="qmt:read"),
        jwt.encode(
            unsigned_claims, "shared-secret-that-is-at-least-32-bytes", algorithm="HS256", headers={"kid": "key-1"}
        ),
        jwt.encode(unsigned_claims, "", algorithm="none", headers={"kid": "key-1"}),
    ]
    assert all(anyio.run(verifier.verify_token, token) is None for token in invalid_tokens)


def test_jwks_unknown_kid_refresh_accepts_rotated_key(tmp_path):
    first_private, first_public = _key("key-1")
    second_private, second_public = _key("key-2")
    documents = [{"keys": [first_public]}, {"keys": [first_public, second_public]}]

    def fetcher():
        return documents.pop(0)

    verifier = JwtTokenVerifier(_config(tmp_path), fetcher=fetcher)
    assert anyio.run(verifier.verify_token, _token(first_private, "key-1", "qmt:read")) is not None
    assert anyio.run(verifier.verify_token, _token(second_private, "key-2", "qmt:read")) is not None


def test_jwks_failure_is_negatively_cached():
    calls = 0

    def failing_fetcher():
        nonlocal calls
        calls += 1
        raise OSError("offline")

    cache = JwksCache(
        "https://auth.example.com/jwks.json",
        ttl_s=30,
        timeout_s=1,
        max_bytes=1024,
        fetcher=failing_fetcher,
    )
    with pytest.raises(OSError):
        cache.key("unknown", algorithm="RS256")
    assert cache.key("unknown", algorithm="RS256") is None
    assert calls == 1


def test_jwks_redirects_are_rejected_before_following(monkeypatch):
    seen_handler = None

    class _FakeOpener:
        def open(self, request, timeout):
            assert timeout == 1
            return seen_handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "http://169.254.169.254/latest/meta-data",
            )

    def fake_build_opener(handler):
        nonlocal seen_handler
        seen_handler = handler
        return _FakeOpener()

    monkeypatch.setattr(auth_module, "build_opener", fake_build_opener)
    with pytest.raises(ValueError, match="redirects are not allowed"):
        auth_module._open_jwks(Request("https://auth.example.com/jwks.json"), 1)


def test_jwks_rejects_oversized_and_duplicate_key_documents(tmp_path, monkeypatch):
    _private, public = _key("duplicate")
    cache = JwksCache(
        "https://auth.example.com/jwks.json",
        ttl_s=30,
        timeout_s=1,
        max_bytes=32,
    )
    monkeypatch.setattr(auth_module, "_open_jwks", lambda _request, timeout: _Response({"padding": "x" * 100}))
    with pytest.raises(ValueError, match="exceeds configured limit"):
        cache._fetch_url()

    duplicate_cache = JwksCache(
        "https://auth.example.com/jwks.json",
        ttl_s=30,
        timeout_s=1,
        max_bytes=1024,
        fetcher=lambda: {"keys": [public, public]},
    )
    with pytest.raises(ValueError, match="unique non-empty kid"):
        duplicate_cache.key("duplicate", algorithm="RS256")


def test_oauth_tools_list_and_modern_scope_step_up(fake_xtquant, tmp_path, monkeypatch):
    private, public = _key("key-1")
    _install_jwks(monkeypatch, {"keys": [public]})
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    list_payload, list_headers = _request("tools/list", 1)
    call_payload, call_headers = _request("tools/call", 2, name="qmt_xtdata_snapshot")

    with TestClient(app, base_url="https://qmt.example.com") as client:
        core_token = _token(private, "key-1", "qmt:read")
        listed = client.post(
            "/mcp",
            json=list_payload,
            headers={**list_headers, "authorization": f"Bearer {core_token}"},
        )
        refused = client.post(
            "/mcp",
            json=call_payload,
            headers={**call_headers, "authorization": f"Bearer {core_token}"},
        )
        market_token = _token(private, "key-1", "qmt:read qmt:market")
        market_listed = client.post(
            "/mcp",
            json=list_payload,
            headers={**list_headers, "authorization": f"Bearer {market_token}"},
        )
        manage_token = _token(private, "key-1", "qmt:read qmt:market qmt:manage")
        manage_listed = client.post(
            "/mcp",
            json=list_payload,
            headers={**list_headers, "authorization": f"Bearer {manage_token}"},
        )

    assert listed.status_code == 200
    assert {tool["name"] for tool in _response_json(listed)["result"]["tools"]} == {
        "qmt_health",
        "qmt_capabilities",
    }
    assert refused.status_code == 403
    assert refused.json()["error_type"] == "insufficient_scope"
    challenge = refused.headers["www-authenticate"]
    assert 'error="insufficient_scope"' in challenge
    assert 'scope="qmt:market"' in challenge
    assert f'resource="{RESOURCE}"' in challenge

    market_names = {tool["name"] for tool in _response_json(market_listed)["result"]["tools"]}
    assert "qmt_xtdata_snapshot" in market_names
    assert "qmt_xtdata_download_history" not in market_names
    manage_names = {tool["name"] for tool in _response_json(manage_listed)["result"]["tools"]}
    assert "qmt_xtdata_download_history" in manage_names


def test_hybrid_static_token_preserves_startup_visible_surface(fake_xtquant, tmp_path, monkeypatch):
    _private, public = _key("key-1")
    _install_jwks(monkeypatch, {"keys": [public]})
    app, _cfg, _health, registry = create_app(_config(tmp_path, auth_mode="hybrid", token="static-secret"))
    list_payload, list_headers = _request("tools/list", 1)

    with TestClient(app, base_url="https://qmt.example.com") as client:
        listed = client.post(
            "/mcp",
            json=list_payload,
            headers={**list_headers, "authorization": "Bearer static-secret"},
        )

    assert listed.status_code == 200
    assert {tool["name"] for tool in _response_json(listed)["result"]["tools"]} == set(registry.tool_names())


def test_oauth_tasks_bind_stable_principal_and_original_scopes(fake_xtquant, tmp_path, monkeypatch):
    private, public = _key("key-1")
    _install_jwks(monkeypatch, {"keys": [public]})
    app, _cfg, _health, _registry = create_app(_config(tmp_path, task_store=str(tmp_path / "oauth-tasks.sqlite3")))
    create_payload, create_headers = _task_request(
        "tools/call",
        1,
        {
            "name": "qmt_xtdata_download_history",
            "arguments": {"code": "510300.SH", "period": "1d"},
        },
    )
    owner = _token(private, "key-1", "qmt:read qmt:market qmt:manage", jti="first")

    with TestClient(app, base_url="https://qmt.example.com") as client:
        created_response = client.post(
            "/mcp",
            json=create_payload,
            headers={**create_headers, "authorization": f"Bearer {owner}"},
        )
        assert created_response.status_code == 200
        task_id = _response_json(created_response)["result"]["taskId"]
        get_payload, get_headers = _task_request("tasks/get", 2, {"taskId": task_id})

        refreshed = _token(private, "key-1", "qmt:read qmt:market qmt:manage", jti="refreshed")
        resumed = client.post(
            "/mcp",
            json=get_payload,
            headers={**get_headers, "authorization": f"Bearer {refreshed}"},
        )
        other_subject = _token(
            private,
            "key-1",
            "qmt:read qmt:market qmt:manage",
            sub="operator-2",
        )
        hidden_owner = client.post(
            "/mcp",
            json=get_payload,
            headers={**get_headers, "authorization": f"Bearer {other_subject}"},
        )
        reduced = _token(private, "key-1", "qmt:read qmt:market", jti="reduced")
        hidden_scope = client.post(
            "/mcp",
            json=get_payload,
            headers={**get_headers, "authorization": f"Bearer {reduced}"},
        )
        update_payload, update_headers = _task_request(
            "tasks/update",
            3,
            {
                "taskId": task_id,
                "inputResponses": {"unknown": {"action": "cancel"}},
            },
        )
        owner_update = client.post(
            "/mcp",
            json=update_payload,
            headers={**update_headers, "authorization": f"Bearer {refreshed}"},
        )
        hidden_update_owner = client.post(
            "/mcp",
            json=update_payload,
            headers={**update_headers, "authorization": f"Bearer {other_subject}"},
        )
        hidden_update_scope = client.post(
            "/mcp",
            json=update_payload,
            headers={**update_headers, "authorization": f"Bearer {reduced}"},
        )

    assert resumed.status_code == 200
    assert _response_json(resumed)["result"]["taskId"] == task_id
    assert owner_update.status_code == 200
    assert _response_json(owner_update)["result"]["resultType"] == "complete"
    for hidden in (hidden_owner, hidden_scope, hidden_update_owner, hidden_update_scope):
        assert hidden.status_code == 400
        document = _response_json(hidden)
        assert document["error"]["code"] == -32602
        assert task_id not in hidden.text


def test_protocol_validation_runs_after_oauth_authentication(fake_xtquant, tmp_path, monkeypatch):
    private, public = _key("key-1")
    _install_jwks(monkeypatch, {"keys": [public]})
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    bearer = f"Bearer {_token(private, 'key-1', 'qmt:read')}"
    legacy = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "oauth-protocol-test", "version": "1.0.0"},
        },
    }

    with TestClient(app, base_url="https://qmt.example.com") as client:
        authenticated = client.post(
            "/mcp",
            json=legacy,
            headers={"accept": "application/json", "authorization": bearer},
        )
        unauthenticated = client.post("/mcp", json=legacy, headers={"accept": "application/json"})

    assert authenticated.status_code == 400
    assert authenticated.json()["error"]["code"] == -32022
    assert "mcp-session-id" not in authenticated.headers
    assert unauthenticated.status_code == 401


def test_oauth_invalid_token_is_401_and_metadata_has_cors(fake_xtquant, tmp_path, monkeypatch):
    _private, public = _key("key-1")
    _install_jwks(monkeypatch, {"keys": [public]})
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    payload, headers = _request("server/discover", 1)

    with TestClient(app, base_url="https://qmt.example.com") as client:
        refused = client.post("/mcp", json=payload, headers={**headers, "authorization": "Bearer invalid"})
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")

    assert refused.status_code == 401
    assert 'scope="qmt:read"' in refused.headers["www-authenticate"]
    assert f'resource="{RESOURCE}"' in refused.headers["www-authenticate"]
    assert metadata.status_code == 200
    assert metadata.headers["access-control-allow-origin"] == "*"
    assert metadata.json()["scopes_supported"] == [
        "qmt:read",
        "qmt:market",
        "qmt:account",
        "qmt:manage",
        "qmt:admin",
    ]


def test_valid_token_without_base_scope_is_403_on_health(fake_xtquant, tmp_path, monkeypatch):
    private, public = _key("key-1")
    _install_jwks(monkeypatch, {"keys": [public]})
    app, _cfg, _health, _registry = create_app(_config(tmp_path))

    with TestClient(app, base_url="https://qmt.example.com") as client:
        response = client.get(
            "/healthz",
            headers={"authorization": f"Bearer {_token(private, 'key-1', 'qmt:market')}"},
        )

    assert response.status_code == 403
    assert response.json()["error_type"] == "insufficient_scope"
    challenge = response.headers["www-authenticate"]
    assert 'scope="qmt:read"' in challenge
    assert 'resource_metadata="https://qmt.example.com/.well-known/oauth-protected-resource/mcp"' in challenge
