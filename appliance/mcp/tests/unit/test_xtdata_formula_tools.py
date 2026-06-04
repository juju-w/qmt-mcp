from __future__ import annotations

from pathlib import Path

from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.workers import WorkerPool
from qmt_mcp_xtdata.formula_tools import register_formula_tools


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
        enable_formula_runtime=True,
        formula_allowlist="VIX_HELPER",
        formula_output_sandbox=str(tmp_path / "formula"),
    )


def registry_with_formula(tmp_path: Path):
    callbacks = {}

    def call(name, *args):
        if name == "call_formula":
            return {"value": 1}
        if name == "call_formula_batch":
            return {"510300.SH": {"value": 1}}
        if name == "generate_index_data":
            return True
        if name == "subscribe_formula":
            callbacks[7] = args[-1]
            return 7
        if name == "unsubscribe_formula":
            return True
        raise AssertionError(name)

    cfg = make_config(tmp_path)
    health = HealthState(cfg)
    audit = JsonlAuditSink(cfg.audit_path, cfg.broker_id)
    audit.initialize()
    registry = ToolRegistry(health, audit, WorkerPool(2))
    register_formula_tools(DummyMCP(), registry, cfg, call)
    return registry, callbacks


def test_formula_call_generate_and_subscribe(tmp_path):
    registry, callbacks = registry_with_formula(tmp_path)
    called = registry._tools["qmt_xtdata_formula_call"]["callable"](formula_name="VIX_HELPER", code="510300.SH")
    assert called["result"] == {"value": 1}

    generated = registry._tools["qmt_xtdata_formula_generate_factor"]["callable"](
        formula_name="VIX_HELPER", result_path="vix.feather"
    )
    assert generated["status"] == "generated"

    sub = registry._tools["qmt_xtdata_formula_subscribe"]["callable"](formula_name="VIX_HELPER", code="510300.SH")
    assert sub["subscription"]["subscription_id"] == 7
    callbacks[7]({"value": 2})
    cache = registry._tools["qmt_xtdata_formula_cache"]["callable"]()
    assert cache["entry_count"] == 1


def test_formula_refuses_unallowlisted(tmp_path):
    registry, _ = registry_with_formula(tmp_path)
    result = registry._tools["qmt_xtdata_formula_call"]["callable"](formula_name="OTHER", code="510300.SH")
    assert result["ok"] is False
    assert result["error_type"] == "validation"
