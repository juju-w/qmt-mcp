from __future__ import annotations

from pathlib import Path

from qmt_mcp_core.audit import JsonlAuditSink
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_core.workers import WorkerPool
from qmt_mcp_xtdata.option_tools import register_option_tools


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


def registry_with_options(tmp_path: Path):
    def call(name, *args):
        if name == "get_option_undl_data":
            return ["510300.SH"]
        if name == "get_option_list":
            return ["10000001.SHO", "10000002.SHO"]
        if name == "get_instrument_detail":
            return {
                "ExchangeID": "SHO",
                "InstrumentID": args[0].split(".")[0],
                "InstrumentName": "300ETF购" if args[0].endswith("1.SHO") else "300ETF沽",
                "ProductID": "300ETF(510300)",
                "ExpireDate": "20260624",
                "OpenDate": "20250101",
                "CreateDate": "20250101",
                "OptUndlCode": "510300",
                "OptUndlMarket": "SH",
                "OptExercisePrice": 4.0,
                "OptionType": 0 if args[0].endswith("1.SHO") else 1,
                "VolumeMultiple": 10000,
            }
        if name == "get_option_detail_data":
            return {
                "code": args[0],
                "undl_code": "510300.SH",
                "opt_type": "C" if args[0].endswith("1.SHO") else "P",
                "strike_price": 4.0,
                "expiry_date": "20260624",
            }
        if name == "get_full_tick":
            return {code: {"lastPrice": 0.1, "bidPrice": [0.09], "askPrice": [0.11]} for code in args[0]}
        if name == "get_option_iv":
            return 0.2
        raise AssertionError(name)

    cfg = make_config(tmp_path)
    health = HealthState(cfg)
    audit = JsonlAuditSink(cfg.audit_path, cfg.broker_id)
    audit.initialize()
    registry = ToolRegistry(health, audit, WorkerPool(2))
    register_option_tools(DummyMCP(), registry, health, call)
    return registry


def test_option_chain_and_quotes(tmp_path):
    registry = registry_with_options(tmp_path)
    chain = registry._tools["qmt_xtdata_option_chain"]["callable"](family="300ETF")
    assert chain["ok"] is True
    assert len(chain["codes"]) == 2
    assert chain["details"][0]["option_type"] == "CALL"

    quotes = registry._tools["qmt_xtdata_option_quotes"]["callable"](codes=chain["codes"])
    assert quotes["quotes"][0]["mid_price"] == 0.1


def test_volatility_index_inputs(tmp_path):
    registry = registry_with_options(tmp_path)
    result = registry._tools["qmt_xtdata_volatility_index_inputs"]["callable"](family="300ETF")
    assert result["ok"] is True
    assert result["underlying_code"] == "510300.SH"
    assert result["diagnostics"]["publishes_index_value"] is False
    assert len(result["rows"]) == 2
