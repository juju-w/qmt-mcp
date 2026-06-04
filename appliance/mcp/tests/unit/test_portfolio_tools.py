from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.workers import WorkerPool
from qmt_mcp_portfolio import tools as portfolio_tools
from qmt_mcp_xttrade.accounts import Allowlist


class DummyMCP:
    def tool(self):
        def decorator(func):
            return func

        return decorator


class FakeSession:
    allowlist = Allowlist.from_config("111111", "STOCK")

    def query(self, method, account_id=None, *args, account_scoped=True):
        if method == "query_stock_asset":
            return SimpleNamespace(m_strAccountID=account_id, m_dCash=1000.0, m_dTotalAsset=10000.0)
        if method == "query_stock_positions":
            return [
                SimpleNamespace(
                    m_strAccountID=account_id,
                    m_strInstrumentID="510300.SH",
                    m_nVolume=1000,
                    m_dAvgPrice=4.0,
                )
            ]
        raise AssertionError(method)


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


def registry_with_portfolio(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        portfolio_tools,
        "_call_xtdata",
        lambda name, codes: {"510300.SH": {"lastPrice": 4.5}},
    )
    cfg = make_config(tmp_path)
    health = HealthState(cfg)
    audit = JsonlAuditSink(cfg.audit_path, cfg.broker_id)
    audit.initialize()
    registry = ToolRegistry(health, audit, WorkerPool(2))
    portfolio_tools.register_portfolio_tools(DummyMCP(), registry, health, FakeSession())
    return registry


def test_portfolio_summary_tool(tmp_path, monkeypatch):
    registry = registry_with_portfolio(tmp_path, monkeypatch)
    tool = registry._tools["qmt_portfolio_summary"]["callable"]
    result = tool(account_id="111111")
    assert result["ok"] is True
    assert result["summary"]["position_count"] == 1
    assert result["summary"]["market_value"] == 4500


def test_portfolio_unknown_account_refused_before_data(tmp_path, monkeypatch):
    registry = registry_with_portfolio(tmp_path, monkeypatch)
    tool = registry._tools["qmt_portfolio_summary"]["callable"]
    result = tool(account_id="222222")
    assert result["ok"] is False
    assert result["error_type"] == "validation"


def test_portfolio_risk_checks_tool(tmp_path, monkeypatch):
    registry = registry_with_portfolio(tmp_path, monkeypatch)
    tool = registry._tools["qmt_portfolio_risk_checks"]["callable"]
    result = tool(account_id="111111", thresholds={"max_single_position_weight": 0.2})
    assert result["ok"] is True
    assert any(check["status"] == "warn" for check in result["checks"])
