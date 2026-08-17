"""Versioned, fully inspectable screening presets."""

from __future__ import annotations

from copy import deepcopy

from qmt_mcp_core.errors import McpCoreError


def _ref(factor_id: str, **params):
    return {"factor_id": factor_id, "params": params}


PRESETS = {
    "etf_rotation": {
        "version": 1,
        "asset_type": "etf",
        "filters": [
            {"factor": _ref("listing_days"), "operator": "gte", "value": 120},
            {"factor": _ref("avg_amount", window=20), "operator": "gte", "value": 50_000_000},
        ],
        "rank": [
            {"factor": _ref("return", window=20), "weight": 0.12, "direction": "higher"},
            {"factor": _ref("return", window=60), "weight": 0.12, "direction": "higher"},
            {"factor": _ref("return", window=120), "weight": 0.10, "direction": "higher"},
            {"factor": _ref("ma_gap", window=60), "weight": 0.20, "direction": "higher"},
            {"factor": _ref("annualized_volatility", window=20), "weight": 0.18, "direction": "lower"},
            {"factor": _ref("max_drawdown", window=60), "weight": 0.18, "direction": "higher"},
            {"factor": _ref("avg_amount", window=20), "weight": 0.10, "direction": "higher"},
        ],
    },
    "etf_execution_quality": {
        "version": 1,
        "asset_type": "etf",
        "filters": [
            {"factor": _ref("listing_days"), "operator": "gte", "value": 250},
            {"factor": _ref("avg_amount", window=20), "operator": "gte", "value": 100_000_000},
        ],
        "rank": [
            {"factor": _ref("avg_amount", window=20), "weight": 0.65, "direction": "higher"},
            {
                "factor": _ref("bid_ask_spread_bps"),
                "weight": 0.35,
                "direction": "lower",
                "missing_policy": "neutral",
            },
        ],
    },
    "stock_industry_strength": {
        "version": 1,
        "asset_type": "stock",
        "filters": [
            {"factor": _ref("listing_days"), "operator": "gte", "value": 250},
            {"factor": _ref("avg_amount", window=60), "operator": "gte", "value": 30_000_000},
            {"factor": _ref("float_market_cap"), "operator": "gte", "value": 5_000_000_000},
        ],
        "rank": [
            {"factor": _ref("sector_relative_strength", window=60), "weight": 0.35},
            {"factor": _ref("return", window=20), "weight": 0.20},
            {"factor": _ref("ma_gap", window=60), "weight": 0.15},
            {"factor": _ref("annualized_volatility", window=20), "weight": 0.15, "direction": "lower"},
            {"factor": _ref("max_drawdown", window=60), "weight": 0.10},
            {"factor": _ref("avg_amount", window=60), "weight": 0.05},
        ],
    },
    "stock_liquid_quality": {
        "version": 1,
        "asset_type": "stock",
        "stock_profile": "non_financial",
        "filters": [
            {"factor": _ref("listing_days"), "operator": "gte", "value": 250},
            {"factor": _ref("avg_amount", window=60), "operator": "gte", "value": 30_000_000},
            {"factor": _ref("float_market_cap"), "operator": "gte", "value": 5_000_000_000},
            {"factor": _ref("earnings_yield_ttm"), "operator": "gt", "value": 0},
        ],
        "rank": [
            {"factor": _ref("earnings_yield_ttm"), "weight": 0.20},
            {"factor": _ref("roe_ttm"), "weight": 0.25},
            {"factor": _ref("cfo_to_net_profit_ttm"), "weight": 0.20},
            {"factor": _ref("debt_to_assets"), "weight": 0.15, "direction": "lower"},
            {"factor": _ref("revenue_growth_yoy"), "weight": 0.10},
            {"factor": _ref("avg_amount", window=60), "weight": 0.10},
        ],
    },
    "stock_low_vol_value": {
        "version": 1,
        "asset_type": "stock",
        "stock_profile": "non_financial",
        "filters": [
            {"factor": _ref("earnings_yield_ttm"), "operator": "gt", "value": 0},
        ],
        "rank": [
            {"factor": _ref("earnings_yield_ttm"), "weight": 0.30},
            {"factor": _ref("pb_mrq"), "weight": 0.20, "direction": "lower"},
            {"factor": _ref("annualized_volatility", window=60), "weight": 0.25, "direction": "lower"},
            {"factor": _ref("max_drawdown", window=250), "weight": 0.25, "direction": "higher"},
        ],
    },
}


def preset_ids() -> list[str]:
    return sorted(PRESETS)


def expand_preset(preset_id: str) -> dict:
    try:
        return deepcopy(PRESETS[preset_id])
    except KeyError as exc:
        raise McpCoreError(
            "validation",
            f"unknown preset_id: {preset_id}",
            {"preset_id": preset_id, "valid_preset_ids": preset_ids()},
        ) from exc
