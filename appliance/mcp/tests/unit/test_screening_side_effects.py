from __future__ import annotations

from qmt_mcp_screening.sources import ScreeningSource


def test_source_adapter_only_uses_read_calls_and_never_hidden_download_formula_trade_or_network():
    calls = []

    def call(name, *args):
        calls.append(name)
        if name == "get_market_data_ex":
            codes = args[1]
            return {code: {"close": {"20260814": 10.0}} for code in codes}
        if name == "get_full_tick":
            return {}
        if name == "get_financial_data":
            return {}
        raise AssertionError(name)

    source = ScreeningSource(call)
    source.daily_bars(["600001.SH"], count=20)
    source.snapshots(["600001.SH"])
    source.financial_tables(["600001.SH"], ["Income"])

    assert calls == ["get_market_data_ex", "get_full_tick", "get_financial_data"]
    forbidden = ("download", "formula", "file", "network", "xttrade", "order", "buy", "sell")
    assert not any(token in name.lower() for name in calls for token in forbidden)
