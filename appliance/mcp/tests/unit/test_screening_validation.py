from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_screening.validation import normalize_screen_request


def _base(**overrides):
    value = {
        "asset_type": "etf",
        "universe": {"kind": "exposure", "values": ["csi_500"]},
        "preset_id": "etf_execution_quality",
        "filters": [],
        "rank": [],
        "sort": [],
        "limit": 5,
    }
    value.update(overrides)
    return value


def test_preset_expands_and_percentage_remains_decimal():
    request = normalize_screen_request(_base())
    assert request["asset_type"] == "etf"
    assert any(item["value"] == 100_000_000 for item in request["filters"])


@pytest.mark.parametrize(
    "filter_value",
    [
        {"factor": {"factor_id": "invented", "params": {}}, "operator": "gte", "value": 1},
        {"factor": {"factor_id": "return", "params": {"window": 17}}, "operator": "gte", "value": 0.1},
        {"factor": {"factor_id": "return", "params": {"window": 20}}, "operator": "in", "value": [0.1]},
    ],
)
def test_invalid_factor_window_or_operator_returns_alternatives(filter_value):
    with pytest.raises(McpCoreError) as exc:
        normalize_screen_request(
            _base(
                preset_id="",
                filters=[filter_value],
                sort=[{"factor": {"factor_id": "return", "params": {"window": 20}}, "direction": "desc"}],
            )
        )
    assert exc.value.error_type == "validation"
    assert exc.value.details


def test_rank_and_sort_are_mutually_exclusive():
    with pytest.raises(McpCoreError):
        normalize_screen_request(
            _base(
                preset_id="",
                rank=[{"factor": {"factor_id": "return", "params": {"window": 20}}, "weight": 1}],
                sort=[{"factor": {"factor_id": "avg_amount", "params": {"window": 20}}, "direction": "desc"}],
            )
        )


def test_neutral_filter_missing_policy_is_rejected():
    with pytest.raises(McpCoreError):
        normalize_screen_request(_base(filter_missing_policy="neutral"))


def test_stock_fundamental_rejects_financial_profile():
    with pytest.raises(McpCoreError) as exc:
        normalize_screen_request(
            {
                "asset_type": "stock",
                "stock_profile": "bank",
                "universe": {"kind": "codes", "values": ["600000.SH"]},
                "filters": [
                    {"factor": {"factor_id": "gross_margin_ttm", "params": {}}, "operator": "gte", "value": 0.2}
                ],
                "sort": [{"factor": {"factor_id": "avg_amount", "params": {"window": 20}}, "direction": "desc"}],
            }
        )
    assert exc.value.details["profile"] == "bank"
