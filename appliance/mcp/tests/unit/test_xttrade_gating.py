"""Unit tests for xttrade tool gating: allowlist, readiness, no-write (feature 004)."""

from __future__ import annotations

from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.workers import WorkerPool
from qmt_mcp_xttrade.accounts import Allowlist
from qmt_mcp_xttrade.session import TraderSession
from qmt_mcp_xttrade.tools import register_xttrade_tools


class FakeMCP:
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
        test_mode=True,
    )


def _registry(tmp_audit_path):
    health = HealthState(_config())
    audit = JsonlAuditSink(tmp_audit_path, "acme")
    audit.initialize()
    return ToolRegistry(health, audit, WorkerPool(2)), FakeMCP()


def _register(tmp_audit_path):
    reg, mcp = _registry(tmp_audit_path)
    allow = Allowlist.from_config("111111", "STOCK")
    session = TraderSession("/broker/userdata_mini", allow)  # not connected (_trader is None)
    register_xttrade_tools(mcp, reg, reg.health, session, allow)
    return reg, session


def test_only_query_tools_registered_no_write(tmp_audit_path):
    reg, _session = _register(tmp_audit_path)
    names = reg.tool_names("xttrade_query")
    assert "qmt_xttrade_asset" in names
    assert "qmt_xttrade_orders" in names  # a read listing — must be allowed
    # The no-write assertion must NOT false-positive on the read-only "orders" tool.
    reg.assert_no_write_tools()
    assert not any(("place" in n or "cancel" in n or "transfer" in n) for n in names)


def test_unknown_account_refused(tmp_audit_path):
    reg, _session = _register(tmp_audit_path)
    result = reg._tools["qmt_xttrade_asset"]["callable"]("999999")
    assert result["ok"] is False
    assert result["error_type"] == "validation"


def test_trader_not_ready_when_session_unconnected(tmp_audit_path):
    reg, _session = _register(tmp_audit_path)
    # allow-listed account, but the session never connected -> trader-not-ready
    result = reg._tools["qmt_xttrade_positions"]["callable"]("111111")
    assert result["ok"] is False
    assert result["error_type"] == "not_ready"
