from __future__ import annotations

from pathlib import Path

from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.workers import WorkerPool
from qmt_mcp_xtdata import tools


class DummyMCP:
    def tool(self):
        def decorator(func):
            return func

        return decorator


def make_config(tmp_path: Path) -> CoreConfig:
    return CoreConfig(
        broker_id="acme",
        broker_name="ACME",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token="s3cret",
        host="0.0.0.0",
        port=8765,
        transport="streamable-http",
        audit_path=str(tmp_path / "audit.jsonl"),
        worker_limit=2,
        allow_unauth_loopback=False,
        enable_xtdata=True,
        test_mode=False,
        quote_subscription_store=str(tmp_path / "subs.json"),
    )


def registry_with_tools(tmp_path: Path, monkeypatch):
    calls = []
    callbacks = {}

    def fake_call(name, *args, **kwargs):
        calls.append((name, args))
        if name == "subscribe_quote":
            callbacks[1] = args[-1]
            return 1
        if name == "unsubscribe_quote":
            return True
        if name == "get_full_tick":
            return {code: {"lastPrice": 3.0} for code in args[0]}
        return {}

    monkeypatch.setattr(tools, "_call_xtdata", fake_call)
    monkeypatch.setattr(tools, "_xtdata", lambda: object())
    cfg = make_config(tmp_path)
    health = HealthState(cfg)
    audit = JsonlAuditSink(cfg.audit_path, cfg.broker_id)
    audit.initialize()
    registry = ToolRegistry(health, audit, WorkerPool(2))
    tools.register_xtdata_tools(DummyMCP(), registry, health)
    return registry, calls, callbacks


def test_quote_tools_subscribe_and_cache_policy(tmp_path, monkeypatch):
    registry, calls, callbacks = registry_with_tools(tmp_path, monkeypatch)
    subscribe = registry._tools["qmt_xtdata_quote_subscribe"]["callable"]
    snapshot = registry._tools["qmt_xtdata_snapshot"]["callable"]

    result = subscribe(codes=["510300.SH"], subscription_id="s1")
    assert result["ok"] is True
    assert result["subscription"]["active_backend"] == "official_subscription"

    callbacks[1]({"lastPrice": 4.2})
    cached = snapshot(codes=["510300.SH"], cache_policy="cache_only")
    assert cached["ok"] is True
    assert cached["data"][0]["last_price"] == 4.2
    assert not any(call[0] == "get_full_tick" for call in calls)


def test_snapshot_cache_only_missing_returns_error(tmp_path, monkeypatch):
    registry, _, _ = registry_with_tools(tmp_path, monkeypatch)
    snapshot = registry._tools["qmt_xtdata_snapshot"]["callable"]
    result = snapshot(codes=["510300.SH"], cache_policy="cache_only")
    assert result["ok"] is False
    assert result["error_type"] == "not_ready"
