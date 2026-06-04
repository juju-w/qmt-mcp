"""Pure portfolio analysis calculations for 014."""

from __future__ import annotations

from typing import Any

from .thresholds import validate_thresholds


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _market(code: str) -> str:
    return code.split(".")[-1] if "." in code else "UNKNOWN"


def _instrument_type(code: str) -> str:
    if code.endswith((".SH", ".SZ")) and (code.startswith(("51", "15", "58"))):
        return "ETF"
    if code.endswith((".SH", ".SZ", ".BJ")):
        return "STOCK"
    return "OTHER"


def enrich_positions(asset: dict[str, Any] | None, positions: list[dict[str, Any]], quotes: dict[str, dict[str, Any]]):
    asset = asset or {}
    rows: list[dict[str, Any]] = []
    diagnostics = {"missing_quotes": [], "missing_cost": []}
    total_market_value = 0.0

    for pos in positions:
        code = str(pos.get("code") or "")
        volume = _num(pos.get("volume"))
        quote = quotes.get(code) or {}
        price = _num(quote.get("last_price"), 0.0)
        broker_market_value = _num(pos.get("market_value"), 0.0)
        market_value = broker_market_value or (price * volume if price else 0.0)
        total_market_value += market_value
        avg_price = _num(pos.get("avg_price"), 0.0) or _num(pos.get("open_price"), 0.0)
        cost_value = avg_price * volume if avg_price and volume else None
        if code and not quote:
            diagnostics["missing_quotes"].append(code)
        if cost_value is None:
            diagnostics["missing_cost"].append(code)
        rows.append(
            {
                **pos,
                "code": code,
                "volume": volume,
                "quote": quote or None,
                "last_price": price or None,
                "market_value": market_value,
                "cost_value": cost_value,
                "unrealized_pnl": market_value - cost_value if cost_value is not None else None,
                "market": _market(code),
                "instrument_type": _instrument_type(code),
            }
        )

    denominator = _num(asset.get("total_asset"), 0.0) or total_market_value
    for row in rows:
        row["weight"] = row["market_value"] / denominator if denominator else 0.0

    rows.sort(key=lambda item: item["market_value"], reverse=True)
    return rows, {"total_market_value": total_market_value, "denominator": denominator, **diagnostics}


def concentration(rows: list[dict[str, Any]], top_n: int = 5) -> dict[str, Any]:
    weights = sorted([_num(row.get("weight")) for row in rows], reverse=True)
    return {
        "position_count": len(rows),
        "max_position_weight": weights[0] if weights else 0.0,
        "top_n": top_n,
        "top_n_weight": sum(weights[:top_n]),
    }


def exposure(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for row in rows:
        key = str(row.get(field) or "UNKNOWN")
        totals[key] = totals.get(key, 0.0) + _num(row.get("market_value"))
    total = sum(totals.values())
    return [
        {"group": key, "market_value": value, "weight": value / total if total else 0.0}
        for key, value in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]


def portfolio_summary(
    asset: dict[str, Any] | None, rows: list[dict[str, Any]], valuation: dict[str, Any]
) -> dict[str, Any]:
    asset = asset or {}
    cash = _num(asset.get("cash"), 0.0)
    total_asset = _num(asset.get("total_asset"), 0.0) or valuation["denominator"]
    quote_covered = len([row for row in rows if row.get("quote")])
    return {
        "asset": asset,
        "cash": cash,
        "total_asset": total_asset,
        "cash_ratio": cash / total_asset if total_asset else 0.0,
        "market_value": valuation["total_market_value"],
        "position_count": len(rows),
        "quote_coverage": quote_covered / len(rows) if rows else 1.0,
        "top_positions": rows[:5],
        "concentration": concentration(rows),
        "diagnostics": {
            "missing_quotes": valuation["missing_quotes"],
            "missing_cost": valuation["missing_cost"],
        },
    }


def risk_checks(summary: dict[str, Any], thresholds: dict | None = None) -> list[dict[str, Any]]:
    limits = validate_thresholds(thresholds)
    checks = [
        (
            "max_single_position_weight",
            summary["concentration"]["max_position_weight"],
            "<=",
            limits["max_single_position_weight"],
        ),
        ("max_top5_weight", summary["concentration"]["top_n_weight"], "<=", limits["max_top5_weight"]),
        ("min_cash_ratio", summary["cash_ratio"], ">=", limits["min_cash_ratio"]),
        ("min_quote_coverage", summary["quote_coverage"], ">=", limits["min_quote_coverage"]),
    ]
    out = []
    for name, value, op, limit in checks:
        passed = value <= limit if op == "<=" else value >= limit
        out.append(
            {"name": name, "status": "pass" if passed else "warn", "value": value, "operator": op, "limit": limit}
        )
    return out
