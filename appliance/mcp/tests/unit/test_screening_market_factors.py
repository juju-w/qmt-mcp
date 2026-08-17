from __future__ import annotations

import math
import statistics

import pytest

from qmt_mcp_screening.market_factors import calculate_market_factor
from tests.screening_fixtures import daily_rows


def value(factor_id: str, *, closes: list[float], params: dict | None = None, **kwargs) -> float:
    observation = calculate_market_factor(
        code="600001.SH",
        factor_id=factor_id,
        params=params or {},
        bars=daily_rows("600001.SH", closes),
        **kwargs,
    )
    assert observation.status == "available", observation
    return observation.value


def test_adjusted_return_and_moving_average_factors_are_hand_calculable():
    closes = [10.0, 11.0, 12.0, 13.0]

    assert value("return", closes=closes, params={"window": 3}) == pytest.approx(0.3)
    assert value("ma_gap", closes=closes, params={"window": 3}) == pytest.approx(13 / 12 - 1)

    alignment = calculate_market_factor(
        code="600001.SH",
        factor_id="ma_alignment",
        params={},
        bars=daily_rows("600001.SH", [float(number) for number in range(1, 122)]),
    )
    assert alignment.value == "bullish"
    assert alignment.adjustment == "front_ratio"


def test_volatility_drawdown_amount_and_trading_coverage():
    closes = [100.0, 110.0, 99.0, 118.8]
    returns = [0.10, -0.10, 0.20]
    assert value("annualized_volatility", closes=closes, params={"window": 3}) == pytest.approx(
        statistics.stdev(returns) * math.sqrt(252)
    )
    assert value("max_drawdown", closes=closes, params={"window": 4}) == pytest.approx(-0.10)

    bars = daily_rows("600001.SH", [10, 10, 10], amount=30.0)
    bars[-1]["amount"] = 60.0
    assert calculate_market_factor(
        code="600001.SH", factor_id="avg_amount", params={"window": 3}, bars=bars
    ).value == pytest.approx(40.0)
    assert calculate_market_factor(
        code="600001.SH", factor_id="amount_ratio", params={"window": 2}, bars=bars
    ).value == pytest.approx(2.0)

    bars[1]["suspendFlag"] = 1
    assert calculate_market_factor(
        code="600001.SH", factor_id="trading_ratio", params={"window": 3}, bars=bars
    ).value == pytest.approx(2 / 3)


def test_stock_liquidity_size_and_peer_relative_factors():
    bars = daily_rows("600001.SH", [10.0, 11.0, 9.9], amount=100_000_000.0)
    instrument = {"float_shares": 10_000_000.0, "total_shares": 20_000_000.0}

    float_cap = calculate_market_factor(
        code="600001.SH", factor_id="float_market_cap", params={}, bars=bars, instrument=instrument
    )
    assert float_cap.value == pytest.approx(99_000_000.0)
    assert float_cap.adjustment == "none"
    assert calculate_market_factor(
        code="600001.SH", factor_id="total_market_cap", params={}, bars=bars, instrument=instrument
    ).value == pytest.approx(198_000_000.0)
    assert calculate_market_factor(
        code="600001.SH",
        factor_id="turnover_rate",
        params={"window": 2},
        bars=bars,
        instrument=instrument,
    ).value == pytest.approx(0.1)

    amihud = calculate_market_factor(code="600001.SH", factor_id="amihud_illiquidity", params={"window": 2}, bars=bars)
    assert amihud.value == pytest.approx(((0.1 / 100_000_000) + (0.1 / 100_000_000)) / 2 * 1e8)
    assert amihud.details["scale"] == 100_000_000

    relative = calculate_market_factor(
        code="600001.SH",
        factor_id="sector_relative_strength",
        params={"window": 2},
        bars=bars,
        peer_returns=[-0.1, 0.0, 0.1],
    )
    assert relative.value == pytest.approx(-0.01)


def test_missing_history_and_invalid_spread_are_typed_not_zero():
    missing = calculate_market_factor(
        code="600001.SH",
        factor_id="return",
        params={"window": 20},
        bars=daily_rows("600001.SH", [10, 11]),
    )
    assert missing.status == "missing"
    assert missing.missing_reason == "insufficient_history"

    one_sided = calculate_market_factor(
        code="600001.SH",
        factor_id="bid_ask_spread_bps",
        params={},
        bars=[],
        snapshot={"bid1": 0, "ask1": 10.01},
    )
    assert one_sided.status == "missing"
    assert one_sided.missing_reason == "one_sided_quote"
