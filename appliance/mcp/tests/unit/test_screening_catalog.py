from __future__ import annotations

from qmt_mcp_screening.catalog import FACTOR_VERSION, catalog_for, factor_definition
from qmt_mcp_screening.presets import expand_preset, preset_ids


def test_catalog_contains_declared_p0_factor_families():
    stock = {item["factor_id"] for item in catalog_for("stock", capabilities={"daily_bars", "financial_data"})}
    etf = {item["factor_id"] for item in catalog_for("etf", capabilities={"daily_bars", "snapshot"})}
    assert FACTOR_VERSION == "screening-factors-v1"
    assert {"return", "avg_amount", "annualized_volatility", "max_drawdown"} <= stock & etf
    assert {
        "float_market_cap",
        "earnings_yield_ttm",
        "roe_ttm",
        "cfo_to_net_profit_ttm",
        "debt_to_assets",
    } <= stock
    assert {"tracking_error", "premium_to_iopv", "portfolio_overlap"} <= etf


def test_catalog_keeps_unavailable_definitions_visible_with_reason():
    item = next(row for row in catalog_for("etf", capabilities={"daily_bars"}) if row["factor_id"] == "premium_to_iopv")
    assert item["availability"] == "unavailable"
    assert item["required_capabilities"] == ["etf_iopv", "snapshot"]
    assert item["availability_reason"]


def test_runtime_capability_overlay_is_truthful_without_hiding_p0_definitions():
    stock = catalog_for("stock", capabilities={"daily_bars", "instrument_detail"}, include_unavailable=False)
    earnings = next(item for item in stock if item["factor_id"] == "earnings_yield_ttm")
    assert earnings["availability"] == "unavailable"
    assert "financial_data" in earnings["availability_reason"]

    etf = catalog_for("etf", capabilities={"daily_bars", "snapshot", "etf_iopv"})
    premium = next(item for item in etf if item["factor_id"] == "premium_to_iopv")
    assert premium["availability"] == "unavailable"
    assert "screening_implementation" in premium["availability_reason"]
    assert next(item for item in etf if item["factor_id"] == "portfolio_overlap")["availability"] == "unavailable"


def test_factor_parameters_and_decimal_domains_are_machine_readable():
    definition = factor_definition("return")
    assert definition.parameters["window"]["allowed"] == [5, 20, 60, 120]
    assert definition.domain["minimum"] == -1
    assert definition.unit == "ratio"


def test_five_ranking_presets_expand_to_explicit_rules():
    assert set(preset_ids()) == {
        "etf_execution_quality",
        "etf_rotation",
        "stock_industry_strength",
        "stock_liquid_quality",
        "stock_low_vol_value",
    }
    expanded = expand_preset("etf_execution_quality")
    assert expanded["asset_type"] == "etf"
    assert expanded["filters"]
    assert expanded["rank"]
