from __future__ import annotations

import pytest

from qmt_mcp_screening.financial_factors import FinancialTimeline, calculate_financial_factor


def timeline(*, profit: float = 19.0, prior_profit: float = 8.0) -> FinancialTimeline:
    return FinancialTimeline(
        {
            "Income": [
                {
                    "report_date": "20230930",
                    "announce_time": "20231020",
                    "revenue": 80,
                    "net_profit": prior_profit,
                    "gross_profit": 32,
                },
                {
                    "report_date": "20231231",
                    "announce_time": "20240320",
                    "revenue": 120,
                    "net_profit": 12,
                    "gross_profit": 48,
                },
                {
                    "report_date": "20240930",
                    "announce_time": "20241020",
                    "revenue": 100,
                    "net_profit": profit,
                    "gross_profit": 40,
                },
            ],
            "CashFlow": [
                {"report_date": "20230930", "announce_time": "20231020", "operating_cash_flow": 10},
                {"report_date": "20231231", "announce_time": "20240320", "operating_cash_flow": 14},
                {"report_date": "20240930", "announce_time": "20241020", "operating_cash_flow": 18},
            ],
            "Balance": [
                {
                    "report_date": "20230930",
                    "announce_time": "20231020",
                    "total_assets": 200,
                    "total_liabilities": 80,
                    "equity": 100,
                },
                {
                    "report_date": "20231231",
                    "announce_time": "20240320",
                    "total_assets": 220,
                    "total_liabilities": 85,
                    "equity": 999,
                },
                {
                    "report_date": "20240930",
                    "announce_time": "20241020",
                    "total_assets": 240,
                    "total_liabilities": 90,
                    "equity": 150,
                },
            ],
        },
        as_of="20241101",
    )


def factor(factor_id: str, *, data: FinancialTimeline | None = None, market_cap: float = 300.0):
    return calculate_financial_factor(
        code="600001.SH",
        factor_id=factor_id,
        timeline=data or timeline(),
        market_cap=market_cap,
        stock_profile="non_financial",
    )


def test_value_quality_growth_margin_cash_flow_and_leverage_factors():
    assert factor("earnings_yield_ttm").value == pytest.approx(23 / 300)
    assert factor("pb_mrq").value == pytest.approx(2.0)
    assert factor("roe_ttm").value == pytest.approx(23 / 125)
    assert factor("revenue_growth_yoy").value == pytest.approx(0.25)
    assert factor("net_profit_growth_yoy").value == pytest.approx(19 / 8 - 1)
    assert factor("gross_margin_ttm").value == pytest.approx(0.4)
    assert factor("cfo_to_net_profit_ttm").value == pytest.approx(22 / 23)
    assert factor("debt_to_assets").value == pytest.approx(90 / 240)
    assert factor("asset_growth_yoy").value == pytest.approx(0.2)


def test_negative_earnings_are_valid_but_sign_crossing_growth_is_missing():
    data = timeline(profit=-20, prior_profit=8)
    earnings = factor("earnings_yield_ttm", data=data)
    assert earnings.status == "available"
    assert earnings.value == pytest.approx(-16 / 300)

    growth = factor("net_profit_growth_yoy", data=data)
    assert growth.status == "missing"
    assert growth.missing_reason == "non_comparable_denominator"
    quality = factor("cfo_to_net_profit_ttm", data=data)
    assert quality.status == "missing"
    assert quality.missing_reason == "non_comparable_denominator"


def test_zero_denominators_and_profile_mismatch_are_typed_missing_values():
    data = timeline(prior_profit=0)
    assert factor("net_profit_growth_yoy", data=data).missing_reason == "non_comparable_denominator"

    incompatible = calculate_financial_factor(
        code="600001.SH",
        factor_id="roe_ttm",
        timeline=timeline(),
        market_cap=300,
        stock_profile="bank",
    )
    assert incompatible.status == "not_applicable"
    assert incompatible.missing_reason == "profile_incompatible"
