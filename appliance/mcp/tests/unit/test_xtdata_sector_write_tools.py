from __future__ import annotations

from pathlib import Path

from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.workers import WorkerPool
from qmt_mcp_xtdata.sector_write_tools import register_sector_write_tools


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
        enable_xtdata_sector_write=True,
    )


def registry_with_sector_write(tmp_path: Path):
    calls = []

    def call(name, *args):
        calls.append((name, args))
        if name == "get_sector_list":
            return ["MCP/Test", "沪深A股"]
        return True

    cfg = make_config(tmp_path)
    health = HealthState(cfg)
    audit = JsonlAuditSink(cfg.audit_path, cfg.broker_id)
    audit.initialize()
    registry = ToolRegistry(health, audit, WorkerPool(2))
    register_sector_write_tools(DummyMCP(), registry, cfg, call)
    return registry, calls


def test_sector_create_add_and_list(tmp_path):
    registry, calls = registry_with_sector_write(tmp_path)
    created = registry._tools["qmt_xtdata_sector_create"]["callable"](sector="MCP/Test")
    assert created["ok"] is True
    added = registry._tools["qmt_xtdata_sector_add_codes"]["callable"](sector="MCP/Test", codes=["510300.SH"])
    assert added["codes"] == ["510300.SH"]
    managed = registry._tools["qmt_xtdata_managed_sector_list"]["callable"]()
    assert managed["sectors"] == ["MCP/Test"]
    assert calls[0][0] == "create_sector"


def test_sector_refuses_unmanaged_and_requires_confirm(tmp_path):
    registry, _ = registry_with_sector_write(tmp_path)
    result = registry._tools["qmt_xtdata_sector_create"]["callable"](sector="User/Test")
    assert result["ok"] is False
    delete_result = registry._tools["qmt_xtdata_sector_delete"]["callable"](sector="MCP/Test")
    assert delete_result["ok"] is False
