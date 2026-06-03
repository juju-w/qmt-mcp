"""Unit tests for the tool registry: no-write guarantee + audit wrapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.workers import WorkerPool


class FakeMCP:
    """Minimal stand-in for FastMCP: records tools registered via .tool()."""

    def __init__(self):
        self.registered = []

    def tool(self):
        def deco(fn):
            self.registered.append(fn.__name__)
            return fn

        return deco


def _config() -> CoreConfig:
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
        audit_path="/tmp/a.jsonl",
        worker_limit=2,
        allow_unauth_loopback=False,
        enable_xtdata=True,
        test_mode=False,
    )


def _make_registry(tmp_audit_path):
    health = HealthState(_config())
    audit = JsonlAuditSink(tmp_audit_path, "acme")
    audit.initialize()
    return ToolRegistry(health, audit, WorkerPool(2)), FakeMCP(), audit


def test_read_only_set_passes_no_write_assertion(tmp_audit_path):
    reg, mcp, _ = _make_registry(tmp_audit_path)

    @reg.register(mcp, name="qmt_snapshot", family="xtdata", description="read snapshot")
    def qmt_snapshot():
        return {"ok": True}

    reg.assert_no_write_tools()  # must not raise
    assert "qmt_snapshot" in reg.tool_names()
    assert "qmt_snapshot" in mcp.registered


def test_planted_write_tool_is_detected(tmp_audit_path):
    reg, mcp, _ = _make_registry(tmp_audit_path)

    @reg.register(mcp, name="place_order", family="xttrade", description="DANGER")
    def place_order():
        return {"ok": True}

    with pytest.raises(McpCoreError) as exc:
        reg.assert_no_write_tools()
    assert "place_order" in exc.value.details["tools"]


def test_duplicate_registration_rejected(tmp_audit_path):
    reg, mcp, _ = _make_registry(tmp_audit_path)

    @reg.register(mcp, name="qmt_health", family="core", description="d")
    def a():
        return {"ok": True}

    with pytest.raises(McpCoreError):

        @reg.register(mcp, name="qmt_health", family="core", description="d")
        def b():
            return {"ok": True}


def test_audit_records_ok_outcome(tmp_audit_path):
    reg, mcp, _ = _make_registry(tmp_audit_path)

    @reg.register(mcp, name="qmt_ok", family="core", description="d")
    def qmt_ok():
        return {"ok": True}

    qmt_ok()
    records = [json.loads(line) for line in Path(tmp_audit_path).read_text().splitlines()]
    assert records[-1]["tool"] == "qmt_ok"
    assert records[-1]["outcome"] == "ok"


def test_refused_outcome_on_mcp_core_error(tmp_audit_path):
    reg, mcp, _ = _make_registry(tmp_audit_path)

    @reg.register(mcp, name="qmt_guarded", family="core", description="d")
    def qmt_guarded():
        raise McpCoreError("not_ready", "trader-not-ready")

    result = qmt_guarded()
    assert result["ok"] is False
    assert result["error_type"] == "not_ready"
    records = [json.loads(line) for line in Path(tmp_audit_path).read_text().splitlines()]
    assert records[-1]["outcome"] == "refused"
    assert records[-1]["error_type"] == "not_ready"
