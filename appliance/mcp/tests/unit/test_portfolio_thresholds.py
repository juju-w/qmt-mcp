from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_portfolio.thresholds import DEFAULT_THRESHOLDS, validate_thresholds


def test_validate_thresholds_defaults_and_overrides():
    values = validate_thresholds({"max_single_position_weight": 0.4})
    assert values["max_single_position_weight"] == 0.4
    assert values["min_cash_ratio"] == DEFAULT_THRESHOLDS["min_cash_ratio"]


def test_validate_thresholds_rejects_unknown_and_bounds():
    with pytest.raises(McpCoreError):
        validate_thresholds({"unknown": 0.1})
    with pytest.raises(McpCoreError):
        validate_thresholds({"min_cash_ratio": 2})
