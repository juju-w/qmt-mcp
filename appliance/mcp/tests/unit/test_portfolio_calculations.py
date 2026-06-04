from __future__ import annotations

from qmt_mcp_portfolio.calculations import enrich_positions, exposure, portfolio_summary, risk_checks


def test_enrich_positions_values_weights_and_pnl():
    asset = {"cash": 1000, "total_asset": 11000}
    positions = [
        {"code": "510300.SH", "volume": 1000, "avg_price": 4.0},
        {"code": "159915.SZ", "volume": 1000, "avg_price": 2.0, "market_value": 2500},
    ]
    quotes = {"510300.SH": {"last_price": 4.5}, "159915.SZ": {"last_price": 2.5}}

    rows, valuation = enrich_positions(asset, positions, quotes)
    by_code = {row["code"]: row for row in rows}
    assert by_code["510300.SH"]["market_value"] == 4500
    assert by_code["510300.SH"]["unrealized_pnl"] == 500
    assert round(by_code["510300.SH"]["weight"], 6) == round(4500 / 11000, 6)
    assert valuation["missing_quotes"] == []


def test_summary_exposure_and_risk_checks():
    asset = {"cash": 100, "total_asset": 1000}
    positions = [{"code": "510300.SH", "volume": 100, "avg_price": 5.0}]
    rows, valuation = enrich_positions(asset, positions, {"510300.SH": {"last_price": 9.0}})
    summary = portfolio_summary(asset, rows, valuation)

    assert summary["position_count"] == 1
    assert summary["quote_coverage"] == 1.0
    assert exposure(rows, "market")[0]["group"] == "SH"
    checks = risk_checks(summary, {"max_single_position_weight": 0.8})
    assert any(check["name"] == "max_single_position_weight" and check["status"] == "warn" for check in checks)


def test_missing_quote_does_not_silent_zero_diagnostics():
    rows, valuation = enrich_positions({}, [{"code": "510300.SH", "volume": 100}], {})
    summary = portfolio_summary({}, rows, valuation)
    assert summary["quote_coverage"] == 0
    assert summary["diagnostics"]["missing_quotes"] == ["510300.SH"]
