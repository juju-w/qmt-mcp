from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_screening.models import FactorObservation
from qmt_mcp_screening.ranking import apply_filters, rank_candidates


def observation(code: str, factor_id: str, value, *, reason: str | None = None):
    if reason:
        return FactorObservation.missing(code=code, factor_id=factor_id, params={}, reason=reason, unit="ratio")
    return FactorObservation.available(code=code, factor_id=factor_id, params={}, value=value, unit="ratio")


def candidate(code: str, **values):
    return {
        "code": code,
        "name": code,
        "factors": {factor_id: observation(code, factor_id, value) for factor_id, value in values.items()},
    }


def factor_ref(factor_id: str):
    return {"factor_id": factor_id, "params": {}}


def test_ordered_hard_filters_record_decisions_and_exclude_missing():
    candidates = [
        candidate("A", avg_amount=100, annualized_volatility=0.2),
        candidate("B", avg_amount=10, annualized_volatility=0.1),
        candidate("C", avg_amount=100),
    ]
    filters = [
        {"factor": factor_ref("avg_amount"), "operator": "gte", "value": 50},
        {"factor": factor_ref("annualized_volatility"), "operator": "lte", "value": 0.3},
    ]

    survivors, decisions = apply_filters(candidates, filters, missing_policy="exclude")

    assert [item["code"] for item in survivors] == ["A"]
    assert decisions["B"][0]["passed"] is False
    assert decisions["C"][1]["missing_reason"] == "missing_source_field"


def test_filter_missing_fail_rejects_the_complete_request():
    with pytest.raises(McpCoreError, match="required filter factor is missing"):
        apply_filters(
            [candidate("A")],
            [{"factor": factor_ref("avg_amount"), "operator": "gte", "value": 1}],
            missing_policy="fail",
        )


def test_weighted_direction_aware_percentiles_reconstruct_scores():
    candidates = [
        candidate("A", avg_amount=100, annualized_volatility=0.30),
        candidate("B", avg_amount=200, annualized_volatility=0.20),
        candidate("C", avg_amount=300, annualized_volatility=0.10),
    ]
    rules = [
        {"factor": factor_ref("avg_amount"), "weight": 1, "direction": "higher", "missing_policy": "exclude"},
        {
            "factor": factor_ref("annualized_volatility"),
            "weight": 3,
            "direction": "lower",
            "missing_policy": "exclude",
        },
    ]

    ranked, method = rank_candidates(candidates, rank=rules, sort=[])

    assert [row["code"] for row in ranked] == ["C", "B", "A"]
    assert method["normalized_weights"] == [0.25, 0.75]
    assert ranked[0]["score"] == pytest.approx(100)
    assert ranked[1]["score"] == pytest.approx(50)
    assert ranked[2]["score"] == pytest.approx(0)
    for row in ranked:
        assert row["score"] == pytest.approx(sum(item["contribution"] for item in row["rank_contributions"]))
        assert [item["requested_weight"] for item in row["rank_contributions"]] == [1, 3]
        assert all(item["missing_policy"] == "exclude" for item in row["rank_contributions"])


def test_target_rank_neutral_missing_coverage_and_deterministic_ties():
    rows = [candidate("B", return_=0.05), candidate("A", return_=0.15), candidate("C")]
    for row in rows:
        if "return_" in row["factors"]:
            row["factors"]["return"] = row["factors"].pop("return_")
    rules = [
        {
            "factor": factor_ref("return"),
            "weight": 1,
            "direction": "target",
            "target": 0.10,
            "missing_policy": "neutral",
        }
    ]

    ranked, _method = rank_candidates(rows, rank=rules, sort=[])

    assert ranked[-1]["code"] == "C"
    assert ranked[-1]["coverage"] == 0
    assert ranked[-1]["rank_contributions"][0]["percentile"] == 0.5
    assert [row["code"] for row in ranked[:2]] == ["A", "B"]


def test_winsorization_is_disclosed_for_large_universe_and_raw_values_survive():
    rows = [candidate(f"{index:02d}", avg_amount=float(index)) for index in range(20)]
    rows[-1]["factors"]["avg_amount"] = observation("19", "avg_amount", 1_000_000)
    ranked, method = rank_candidates(
        rows,
        rank=[{"factor": factor_ref("avg_amount"), "weight": 1, "direction": "higher", "missing_policy": "exclude"}],
        sort=[],
    )

    top = ranked[0]["rank_contributions"][0]
    assert method["winsorization"] == [0.01, 0.99]
    assert top["raw_value"] == 1_000_000
    assert top["winsorized_value"] < top["raw_value"]


def test_direct_sort_is_missing_last_with_code_tie_breaker():
    rows = [candidate("B", avg_amount=10), candidate("A", avg_amount=10), candidate("C")]
    ranked, method = rank_candidates(
        rows,
        rank=[],
        sort=[{"factor": factor_ref("avg_amount"), "direction": "desc", "missing_last": True}],
    )
    assert [row["code"] for row in ranked] == ["A", "B", "C"]
    assert method["type"] == "direct_sort"
