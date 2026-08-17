from __future__ import annotations

import inspect
import json
import time
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from starlette.testclient import TestClient

from qmt_mcp_core.app import create_app
from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.tool_contracts import ToolVisibilityPolicy
from qmt_mcp_core.workers import WorkerPool
from qmt_mcp_screening.models import DataContext
from qmt_mcp_screening.service import UniverseResolver
from qmt_mcp_screening.tools import register_screening_tools
from tests.screening_fixtures import daily_rows

pytestmark = pytest.mark.integration

VERSION = "2026-07-28"
TASKS_ID = "io.modelcontextprotocol/tasks"


class DummyMCP:
    def tool(self, **_metadata):
        def decorator(func):
            return func

        return decorator


class DummySource:
    capabilities = frozenset({"daily_bars", "snapshot", "instrument_detail"})


class DummyService:
    source = DummySource()
    limits = {"max_universe_codes": 5000, "max_factor_refs": 24, "max_results": 100}

    def __init__(self):
        self.screen_calls = []

    def screen(self, request):
        self.screen_calls.append(request)
        return {"ok": True, "screen_id": "scr_fixture", "results": [], "stage_counts": {}}

    def explain(self, screen_id, code, *, locale="zh-CN"):
        return {"ok": True, "screen_id": screen_id, "code": code, "state": "selected"}


def config(tmp_path: Path, **overrides) -> CoreConfig:
    values = dict(
        broker_id="fixture",
        broker_name="Fixture",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token="test-token",
        host="127.0.0.1",
        port=8765,
        transport="streamable-http",
        audit_path=str(tmp_path / "audit.jsonl"),
        worker_limit=2,
        allow_unauth_loopback=False,
        enable_xtdata=True,
        test_mode=True,
    )
    values.update(overrides)
    return CoreConfig(**values)


def make_registry(tmp_path: Path, visibility: ToolVisibilityPolicy | None = None):
    cfg = config(tmp_path)
    health = HealthState(cfg)
    audit = JsonlAuditSink(cfg.audit_path, cfg.broker_id)
    audit.initialize()
    registry = ToolRegistry(health, audit, WorkerPool(2), visibility)
    service = DummyService()
    register_screening_tools(DummyMCP(), registry, service)
    return registry, service


def test_catalog_contract_is_read_only_and_makes_no_market_calls(tmp_path):
    registry, _service = make_registry(tmp_path)
    tool = registry._tools["qmt_factor_catalog"]
    result = tool["callable"]("stock", profile="non_financial", locale="en")

    assert result["ok"] is True
    assert result["catalog_version"] == "screening-factors-v1"
    assert result["factors"]
    assert result["limits"]["max_factor_refs"] == 24
    assert tool["behavior"].read_only is True
    assert tool["behavior"].destructive is False
    assert tool["required_scopes"] == ("qmt:read", "qmt:market")


def test_screen_nested_arguments_are_forwarded_and_errors_remain_structured(tmp_path):
    registry, service = make_registry(tmp_path)
    result = registry._tools["qmt_screen_instruments"]["callable"](
        asset_type="etf",
        etf_profile="broad_market_equity",
        universe={"kind": "exposure", "values": ["csi_500"]},
        rank=[{"factor": {"factor_id": "avg_amount", "params": {"window": 20}}, "weight": 1}],
    )
    assert result["screen_id"] == "scr_fixture"
    assert service.screen_calls[0]["universe"]["kind"] == "exposure"

    invalid = registry._tools["qmt_factor_catalog"]["callable"]("crypto")
    assert invalid["ok"] is False
    assert invalid["error_type"] == "validation"


def test_profile_visibility_and_custom_deny_rules(tmp_path):
    for profile in ("full", "readonly", "market"):
        registry, _service = make_registry(tmp_path / profile, ToolVisibilityPolicy(profile))
        assert set(registry.tool_names()) == {
            "qmt_explain_screen_result",
            "qmt_factor_catalog",
            "qmt_screen_instruments",
        }
        assert registry.required_scopes("qmt_screen_instruments") == ("qmt:read", "qmt:market")
    for profile in ("account", "core"):
        registry, _service = make_registry(tmp_path / profile, ToolVisibilityPolicy(profile))
        assert registry.tool_names() == []
    registry, _service = make_registry(
        tmp_path / "denied",
        ToolVisibilityPolicy("custom", allowlist=("qmt_*",), denylist=("qmt_screen_*",)),
    )
    assert "qmt_factor_catalog" in registry.tool_names()
    assert "qmt_screen_instruments" not in registry.tool_names()


def _request(method: str, request_id: int, params: dict, *, tasks: bool) -> tuple[dict, dict]:
    body_params = dict(params)
    extensions = {TASKS_ID: {}} if tasks else {}
    body_params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "screening-test", "version": "1"},
        "io.modelcontextprotocol/clientCapabilities": {"extensions": extensions},
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": VERSION,
        "mcp-method": method,
    }
    headers["mcp-name"] = body_params["name"] if method == "tools/call" else body_params["taskId"]
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params}, headers


def _response_json(response) -> dict:
    if "text/event-stream" not in response.headers.get("content-type", ""):
        return response.json()
    for line in response.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())
    raise AssertionError("missing SSE data event")


def _rpc(client: TestClient, method: str, request_id: int, params: dict, *, tasks: bool = True) -> dict:
    payload, headers = _request(method, request_id, params, tasks=tasks)
    response = client.post("/mcp", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return _response_json(response)


def _screen_service(registry: ToolRegistry):
    original = inspect.unwrap(registry._tools["qmt_screen_instruments"]["callable"])
    return inspect.getclosurevars(original).nonlocals["service"]


def _screen_payload(request: dict) -> dict:
    return {
        "ok": True,
        "screen_id": "scr_transport_fixture",
        "normalized_request": request,
        "stage_counts": {"resolved": 1, "passed_filters": 1, "returned": 0},
        "results": [],
    }


def test_real_mcp_screen_sync_task_cancel_text_and_audit(fake_xtquant, tmp_path):
    cfg = config(
        tmp_path,
        token="",
        allow_unauth_loopback=True,
        task_store=str(tmp_path / "tasks.sqlite3"),
    )
    app, _cfg, _health, registry = create_app(cfg)
    service = _screen_service(registry)

    def fake_screen(request):
        if request["universe"]["values"] == ["SLOW.SH"]:
            time.sleep(0.2)
        return _screen_payload(request)

    service.screen = fake_screen
    arguments = {
        "asset_type": "etf",
        "universe": {"kind": "codes", "values": ["510500.SH"]},
        "sort": [{"factor": {"factor_id": "avg_amount", "params": {"window": 20}}, "direction": "desc"}],
    }
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        synchronous = _rpc(
            client,
            "tools/call",
            1,
            {"name": "qmt_screen_instruments", "arguments": arguments},
            tasks=False,
        )["result"]
        assert synchronous["resultType"] == "complete"
        assert synchronous["structuredContent"]["screen_id"] == "scr_transport_fixture"
        assert "筛选 scr_transport_fixture" in synchronous["content"][0]["text"]

        created = _rpc(
            client,
            "tools/call",
            2,
            {"name": "qmt_screen_instruments", "arguments": arguments},
        )["result"]
        assert created["resultType"] == "task"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            terminal = _rpc(client, "tasks/get", 3, {"taskId": created["taskId"]})["result"]
            if terminal["status"] == "completed":
                break
            time.sleep(0.01)
        assert terminal["result"]["structuredContent"]["screen_id"] == "scr_transport_fixture"
        assert terminal["result"]["isError"] is False

        slow_arguments = {**arguments, "universe": {"kind": "codes", "values": ["SLOW.SH"]}}
        slow = _rpc(
            client,
            "tools/call",
            4,
            {"name": "qmt_screen_instruments", "arguments": slow_arguments},
        )["result"]
        _rpc(client, "tasks/cancel", 5, {"taskId": slow["taskId"]})
        cancelled = _rpc(client, "tasks/get", 6, {"taskId": slow["taskId"]})["result"]
        assert cancelled["status"] == "cancelled"
        time.sleep(0.25)

    audit_rows = [json.loads(line) for line in Path(cfg.audit_path).read_text(encoding="utf-8").splitlines()]
    screen_rows = [row for row in audit_rows if row["tool"] == "qmt_screen_instruments"]
    assert screen_rows
    assert screen_rows[0]["args_summary"]["asset_type"] == "etf"
    assert screen_rows[0]["args_summary"]["universe"]["kind"] == "codes"


def test_real_registry_screen_validation_returns_factor_alternatives(fake_xtquant, tmp_path):
    app, _cfg, _health, registry = create_app(
        config(tmp_path, token="", allow_unauth_loopback=True, task_store=str(tmp_path / "tasks.sqlite3"))
    )
    del app
    result = registry._tools["qmt_screen_instruments"]["callable"](
        asset_type="etf",
        universe={"kind": "codes", "values": ["510500.SH"]},
        rank=[{"factor": {"factor_id": "hallucinated_factor", "params": {}}, "weight": 1}],
    )
    assert result["ok"] is False
    assert result["error_type"] == "validation"
    assert "avg_amount" in result["details"]["valid_factor_ids"]


class NoDbIntegrationSource:
    broker_id = "fixture"
    capabilities = frozenset({"daily_bars", "instrument_detail"})
    errors = ()

    def __init__(self):
        self.daily_calls = 0

    def daily_bars(self, codes, **_kwargs):
        self.daily_calls += 1
        return {code: tuple(daily_rows(code, [10.0] * 21, amount=100_000_000)) for code in codes}

    def data_context(self, *, as_of="", captured_at=""):
        return DataContext(
            captured_at=captured_at,
            as_of=as_of or "20260817",
            market_session="20260817",
            price_adjustment="front_ratio",
            factor_version="screening-factors-v1",
            broker_id=self.broker_id,
        )


def test_no_db_fake_runtime_catalog_task_screen_and_source_free_explanation(fake_xtquant, tmp_path):
    app, cfg, health, registry = create_app(
        config(
            tmp_path,
            token="",
            allow_unauth_loopback=True,
            task_store=str(tmp_path / "tasks.sqlite3"),
            db_url="",
        )
    )
    service = _screen_service(registry)
    source = NoDbIntegrationSource()
    records = [{"code": "600001.SH", "name": "示例制造", "instrument_type": "stock"}]
    sectors = {"银行": [], "证券": [], "保险": []}
    service.source = source
    service.resolver = UniverseResolver(
        cache_provider=lambda: {"records": records},
        sector_provider=lambda sector: sectors.get(sector),
    )
    arguments = {
        "asset_type": "stock",
        "stock_profile": "non_financial",
        "universe": {"kind": "codes", "values": ["600001.SH"]},
        "rank": [
            {"factor": {"factor_id": "avg_amount", "params": {"window": 20}}, "weight": 0.5},
            {
                "factor": {"factor_id": "roe_ttm", "params": {}},
                "weight": 0.5,
                "missing_policy": "neutral",
            },
        ],
    }
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        catalog = _rpc(
            client,
            "tools/call",
            10,
            {
                "name": "qmt_factor_catalog",
                "arguments": {"asset_type": "stock", "profile": "non_financial", "locale": "en"},
            },
        )["result"]
        financial_factor = next(row for row in catalog["structuredContent"]["factors"] if row["factor_id"] == "roe_ttm")
        assert financial_factor["availability"] == "unavailable"

        created = _rpc(
            client,
            "tools/call",
            11,
            {"name": "qmt_screen_instruments", "arguments": arguments},
        )["result"]
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            terminal = _rpc(client, "tasks/get", 12, {"taskId": created["taskId"]})["result"]
            if terminal["status"] == "completed":
                break
            time.sleep(0.01)
        screen = terminal["result"]["structuredContent"]
        assert screen["ok"] is True
        assert screen["results"][0]["coverage"] == 0.5
        assert any("optional factor unavailable: roe_ttm" in warning for warning in screen["warnings"])

        explanation = _rpc(
            client,
            "tools/call",
            13,
            {
                "name": "qmt_explain_screen_result",
                "arguments": {"screen_id": screen["screen_id"], "code": "600001.SH", "locale": "en"},
            },
        )["result"]["structuredContent"]
        assert explanation["selected"] is True
        assert explanation["rank_contributions"][1]["missing_policy"] == "neutral"
        assert source.daily_calls == 1

    assert cfg.db_enabled is False
    assert health.database == "disabled"
