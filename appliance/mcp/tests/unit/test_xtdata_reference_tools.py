from __future__ import annotations

from pathlib import Path

from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.workers import WorkerPool
from qmt_mcp_xtdata.reference_tools import register_reference_tools


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
    )


def registry_with_reference(tmp_path: Path):
    def call(name, *args):
        if name == "get_financial_data":
            return {"600000.SH": {"Income": [{"revenue": 1}]}}
        if name == "download_financial_data":
            return True
        if name == "get_divid_factors":
            return [{"date": "20250101", "factor": 1.0}]
        if name == "get_ipo_info":
            return [{"code": "001234.SZ", "price": 10.0}]
        if name in {"download_cb_data", "download_etf_info"}:
            return True
        if name == "get_cb_info":
            return [{"code": "113000.SH"}]
        if name == "get_etf_info":
            return [{"code": "510300.SH"}]
        if name == "get_period_list":
            return ["1d", "1m"]
        raise AssertionError(name)

    cfg = make_config(tmp_path)
    health = HealthState(cfg)
    audit = JsonlAuditSink(cfg.audit_path, cfg.broker_id)
    audit.initialize()
    registry = ToolRegistry(health, audit, WorkerPool(2))
    register_reference_tools(DummyMCP(), registry, call)
    return registry


def test_financial_and_ipo_reference_tools(tmp_path):
    registry = registry_with_reference(tmp_path)
    financial = registry._tools["qmt_xtdata_financial_data"]["callable"](
        codes=["600000.SH"], tables=["Income"], start_time="20250101"
    )
    assert financial["ok"] is True
    assert financial["data"][0]["table"] == "Income"

    ipo = registry._tools["qmt_xtdata_ipo_info"]["callable"](start_time="20250101", end_time="20250131")
    assert ipo["rows"][0]["code"] == "001234.SZ"


def test_optional_reference_tools(tmp_path):
    registry = registry_with_reference(tmp_path)
    assert registry._tools["qmt_xtdata_dividend_factors"]["callable"](code="510300.SH")["rows"]
    assert registry._tools["qmt_xtdata_cb_info"]["callable"]()["rows"][0]["code"] == "113000.SH"
    assert registry._tools["qmt_xtdata_etf_info"]["callable"](code="510300.SH")["rows"][0]["code"] == "510300.SH"
    assert registry._tools["qmt_xtdata_period_list"]["callable"]()["periods"]
