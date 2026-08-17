"""Versioned screening factor catalog and runtime capability overlay."""

from __future__ import annotations

from typing import Any

from qmt_mcp_core.errors import McpCoreError

from .models import ETF_PROFILES, STOCK_PROFILES, FactorDefinition

FACTOR_VERSION = "screening-factors-v1"
NUMERIC_OPERATORS = ("gt", "gte", "lt", "lte", "between")


def _descriptions(zh: str, en: str) -> dict[str, str]:
    return {"zh-CN": zh, "en": en}


def _factor(
    factor_id: str,
    zh: str,
    en: str,
    *,
    assets: tuple[str, ...] = ("stock", "etf"),
    profiles: tuple[str, ...] = (),
    unit: str = "ratio",
    domain: dict[str, Any] | None = None,
    direction: str = "higher",
    parameters: dict[str, dict[str, Any]] | None = None,
    capabilities: tuple[str, ...] = ("daily_bars",),
    source_class: str = "derived",
    freshness: str = "completed_daily",
    adjustment: str | None = None,
    value_type: str = "number",
    operators: tuple[str, ...] = NUMERIC_OPERATORS,
    formula: str = "",
    presets: tuple[str, ...] = (),
) -> FactorDefinition:
    return FactorDefinition(
        factor_id=factor_id,
        labels={"zh-CN": zh, "en": en},
        descriptions=_descriptions(
            f"{zh}，按目录声明的口径计算。", f"{en}, calculated with catalog-declared semantics."
        ),
        asset_types=assets,
        profiles=profiles,
        value_type=value_type,
        unit=unit,
        domain=dict(domain or {}),
        operators=operators,
        rank_direction=direction,
        parameters=dict(parameters or {}),
        source_class=source_class,
        freshness=freshness,
        point_in_time=True,
        adjustment=adjustment,
        nullable=True,
        required_capabilities=capabilities,
        formula_summary=formula,
        presets=presets,
    )


WINDOW_20_60 = {"window": {"type": "integer", "allowed": [20, 60], "default": 20}}

_DEFINITIONS = [
    _factor(
        "is_trading",
        "交易状态",
        "Trading state",
        unit="state",
        value_type="boolean",
        operators=("eq", "ne"),
        capabilities=("instrument_detail",),
        source_class="native",
        freshness="snapshot",
        direction="neutral",
    ),
    _factor(
        "listing_days",
        "上市天数",
        "Listing days",
        unit="days",
        value_type="integer",
        domain={"minimum": 0},
        capabilities=("instrument_detail",),
        source_class="native",
        direction="higher",
    ),
    _factor(
        "trading_ratio",
        "交易覆盖率",
        "Trading coverage",
        domain={"minimum": 0, "maximum": 1},
        parameters={"window": {"type": "integer", "allowed": [60], "default": 60}},
        formula="valid non-suspended sessions / expected sessions",
    ),
    _factor(
        "avg_amount",
        "平均成交额",
        "Average amount",
        unit="cny",
        domain={"minimum": 0},
        parameters=WINDOW_20_60,
        adjustment="none",
        formula="mean daily amount",
    ),
    _factor(
        "amount_ratio",
        "成交额比",
        "Amount ratio",
        domain={"minimum": 0},
        parameters={
            "window": {"type": "integer", "allowed": [20], "default": 20},
        },
        adjustment="none",
        formula="latest completed amount / preceding-window mean",
    ),
    _factor(
        "bid_ask_spread_bps",
        "买卖价差",
        "Bid-ask spread",
        unit="bps",
        domain={"minimum": 0},
        direction="lower",
        capabilities=("snapshot",),
        source_class="native",
        freshness="snapshot",
        adjustment="none",
        formula="(ask1-bid1)/mid*10000",
    ),
    _factor(
        "return",
        "区间收益率",
        "Window return",
        domain={"minimum": -1},
        parameters={"window": {"type": "integer", "allowed": [5, 20, 60, 120], "default": 20}},
        adjustment="front_ratio",
        formula="adjusted close / lagged adjusted close - 1",
    ),
    _factor(
        "ma_gap",
        "均线偏离",
        "Moving-average gap",
        parameters={"window": {"type": "integer", "allowed": [20, 60, 120], "default": 20}},
        adjustment="front_ratio",
        formula="adjusted close / moving average - 1",
    ),
    _factor(
        "ma_alignment",
        "均线排列",
        "Moving-average alignment",
        unit="state",
        value_type="enum",
        domain={"values": ["bullish", "bearish", "mixed"]},
        operators=("eq", "ne", "in", "not_in"),
        direction="neutral",
        adjustment="front_ratio",
    ),
    _factor(
        "annualized_volatility",
        "年化波动率",
        "Annualized volatility",
        domain={"minimum": 0},
        direction="lower",
        parameters=WINDOW_20_60,
        adjustment="front_ratio",
        formula="stdev(daily return)*sqrt(252)",
    ),
    _factor(
        "max_drawdown",
        "最大回撤",
        "Maximum drawdown",
        domain={"minimum": -1, "maximum": 0},
        direction="higher",
        parameters={"window": {"type": "integer", "allowed": [20, 60, 250], "default": 60}},
        adjustment="front_ratio",
    ),
    _factor(
        "float_market_cap",
        "流通市值",
        "Float market cap",
        assets=("stock",),
        unit="cny",
        domain={"minimum": 0},
        capabilities=("instrument_detail", "daily_bars"),
        adjustment="none",
    ),
    _factor(
        "total_market_cap",
        "总市值",
        "Total market cap",
        assets=("stock",),
        unit="cny",
        domain={"minimum": 0},
        capabilities=("instrument_detail", "daily_bars"),
        adjustment="none",
    ),
    _factor(
        "turnover_rate",
        "换手率",
        "Turnover rate",
        assets=("stock",),
        domain={"minimum": 0},
        parameters=WINDOW_20_60,
        capabilities=("instrument_detail", "daily_bars"),
        adjustment="none",
    ),
    _factor(
        "amihud_illiquidity",
        "Amihud非流动性",
        "Amihud illiquidity",
        assets=("stock",),
        domain={"minimum": 0},
        direction="lower",
        parameters=WINDOW_20_60,
        formula="mean(abs(return)/amount)*1e8",
    ),
    _factor(
        "sector_relative_strength",
        "行业相对强度",
        "Sector-relative strength",
        assets=("stock",),
        parameters=WINDOW_20_60,
        formula="stock return - peer median return",
    ),
    _factor(
        "earnings_yield_ttm",
        "盈利收益率TTM",
        "Earnings yield TTM",
        assets=("stock",),
        profiles=("non_financial",),
        capabilities=("financial_data", "daily_bars"),
        freshness="announced_financial",
    ),
    _factor(
        "pb_mrq",
        "市净率MRQ",
        "Price-to-book MRQ",
        assets=("stock",),
        profiles=("non_financial",),
        unit="score",
        direction="lower",
        capabilities=("financial_data", "daily_bars"),
        freshness="announced_financial",
    ),
    _factor(
        "roe_ttm",
        "净资产收益率TTM",
        "ROE TTM",
        assets=("stock",),
        profiles=("non_financial",),
        capabilities=("financial_data",),
        freshness="announced_financial",
    ),
    _factor(
        "revenue_growth_yoy",
        "营收同比",
        "Revenue growth YoY",
        assets=("stock",),
        profiles=("non_financial",),
        capabilities=("financial_data",),
        freshness="announced_financial",
    ),
    _factor(
        "net_profit_growth_yoy",
        "净利润同比",
        "Net profit growth YoY",
        assets=("stock",),
        profiles=("non_financial",),
        capabilities=("financial_data",),
        freshness="announced_financial",
    ),
    _factor(
        "gross_margin_ttm",
        "毛利率TTM",
        "Gross margin TTM",
        assets=("stock",),
        profiles=("non_financial",),
        capabilities=("financial_data",),
        freshness="announced_financial",
    ),
    _factor(
        "cfo_to_net_profit_ttm",
        "经营现金流利润比",
        "CFO to net profit TTM",
        assets=("stock",),
        profiles=("non_financial",),
        capabilities=("financial_data",),
        freshness="announced_financial",
    ),
    _factor(
        "debt_to_assets",
        "资产负债率",
        "Debt to assets",
        assets=("stock",),
        profiles=("non_financial",),
        domain={"minimum": 0},
        direction="lower",
        capabilities=("financial_data",),
        freshness="announced_financial",
    ),
    _factor(
        "asset_growth_yoy",
        "总资产同比",
        "Asset growth YoY",
        assets=("stock",),
        profiles=("non_financial",),
        capabilities=("financial_data",),
        freshness="announced_financial",
    ),
    _factor(
        "benchmark_relative_return",
        "基准相对收益",
        "Benchmark-relative return",
        assets=("etf",),
        parameters=WINDOW_20_60,
        capabilities=("daily_bars", "benchmark_mapping"),
        adjustment="front_ratio",
    ),
    _factor(
        "benchmark_correlation",
        "基准相关性",
        "Benchmark correlation",
        assets=("etf",),
        domain={"minimum": -1, "maximum": 1},
        parameters={"window": {"type": "integer", "allowed": [60, 120], "default": 60}},
        capabilities=("daily_bars", "benchmark_mapping"),
        adjustment="front_ratio",
    ),
    _factor(
        "tracking_error",
        "跟踪误差",
        "Tracking error",
        assets=("etf",),
        domain={"minimum": 0},
        direction="lower",
        parameters={"window": {"type": "integer", "allowed": [60, 120], "default": 60}},
        capabilities=("daily_bars", "benchmark_mapping"),
        adjustment="front_ratio",
    ),
    _factor(
        "premium_to_iopv",
        "IOPV溢折价率",
        "Premium to IOPV",
        assets=("etf",),
        capabilities=("etf_iopv", "snapshot"),
        source_class="permissioned",
        freshness="snapshot",
        adjustment="none",
    ),
    _factor(
        "abs_premium_to_iopv",
        "绝对IOPV溢折价",
        "Absolute premium to IOPV",
        assets=("etf",),
        domain={"minimum": 0},
        direction="lower",
        capabilities=("etf_iopv", "snapshot"),
        source_class="permissioned",
        freshness="snapshot",
        adjustment="none",
    ),
    _factor(
        "top10_component_weight",
        "前十大成分权重",
        "Top-10 component weight",
        assets=("etf",),
        domain={"minimum": 0, "maximum": 1},
        direction="lower",
        capabilities=("etf_reference",),
        source_class="permissioned",
    ),
    _factor(
        "effective_component_count",
        "有效成分数量",
        "Effective component count",
        assets=("etf",),
        unit="count",
        domain={"minimum": 1},
        capabilities=("etf_reference",),
        source_class="permissioned",
    ),
    _factor(
        "portfolio_overlap",
        "组合重合度",
        "Portfolio overlap",
        assets=("etf",),
        domain={"minimum": 0, "maximum": 1},
        direction="lower",
        capabilities=("etf_reference",),
        source_class="permissioned",
    ),
]

DEFINITIONS = {item.factor_id: item for item in _DEFINITIONS}
P1_FACTORS = frozenset(
    {
        "asset_growth_yoy",
        "benchmark_relative_return",
        "benchmark_correlation",
        "tracking_error",
        "premium_to_iopv",
        "abs_premium_to_iopv",
        "top10_component_weight",
        "effective_component_count",
        "portfolio_overlap",
    }
)
IMPLEMENTED_FACTORS = frozenset(DEFINITIONS) - frozenset(
    {
        "benchmark_relative_return",
        "benchmark_correlation",
        "tracking_error",
        "premium_to_iopv",
        "abs_premium_to_iopv",
        "top10_component_weight",
        "effective_component_count",
        "portfolio_overlap",
    }
)

PROFILES = {
    "stock": sorted(STOCK_PROFILES - {"auto"}),
    "etf": sorted(ETF_PROFILES - {"auto"}),
}


def factor_definition(factor_id: str) -> FactorDefinition:
    try:
        return DEFINITIONS[factor_id]
    except KeyError as exc:
        raise McpCoreError(
            "validation",
            f"unknown factor_id: {factor_id}",
            {"factor_id": factor_id, "valid_factor_ids": sorted(DEFINITIONS)},
        ) from exc


def catalog_for(
    asset_type: str,
    *,
    profile: str = "",
    capabilities: set[str] | frozenset[str] | None = None,
    locale: str = "zh-CN",
    include_unavailable: bool = True,
) -> list[dict[str, Any]]:
    if asset_type not in PROFILES:
        raise McpCoreError("validation", f"invalid asset_type: {asset_type}", {"allowed": sorted(PROFILES)})
    if profile and profile not in PROFILES[asset_type]:
        raise McpCoreError(
            "validation",
            f"invalid {asset_type} profile: {profile}",
            {"allowed": PROFILES[asset_type]},
        )
    active = set(capabilities or ())
    rows = []
    for definition in _DEFINITIONS:
        if asset_type not in definition.asset_types:
            continue
        if profile and definition.profiles and profile not in definition.profiles:
            continue
        missing = sorted(set(definition.required_capabilities) - active)
        if definition.factor_id not in IMPLEMENTED_FACTORS:
            missing.append("screening_implementation")
        row = definition.to_dict(locale=locale)
        row["version"] = FACTOR_VERSION
        row["availability"] = "unavailable" if missing else "available"
        row["availability_reason"] = f"missing runtime capabilities: {', '.join(missing)}" if missing else None
        if include_unavailable or not missing or definition.factor_id not in P1_FACTORS:
            rows.append(row)
    return rows
