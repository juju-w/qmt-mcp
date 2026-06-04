"""Portfolio risk threshold defaults and validation."""

from __future__ import annotations

from qmt_mcp_core.errors import McpCoreError

DEFAULT_THRESHOLDS = {
    "max_single_position_weight": 0.30,
    "max_top5_weight": 0.70,
    "min_cash_ratio": 0.05,
    "min_quote_coverage": 0.95,
}


def validate_thresholds(overrides: dict | None = None) -> dict[str, float]:
    values = dict(DEFAULT_THRESHOLDS)
    for key, value in (overrides or {}).items():
        if key not in values:
            raise McpCoreError("validation", f"unknown risk threshold: {key}", {"allowed": sorted(values)})
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise McpCoreError("validation", f"invalid threshold value: {key}") from exc
        if numeric < 0 or numeric > 1:
            raise McpCoreError("validation", f"threshold out of bounds: {key}", {"min": 0, "max": 1})
        values[key] = numeric
    return values
