"""Ordered filters and explainable comparable-universe ranking."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from qmt_mcp_core.errors import McpCoreError

from .models import FactorObservation, factor_ref_label, finite_number


def _key(factor: dict[str, Any]) -> str:
    return factor_ref_label(str(factor.get("factor_id") or ""), factor.get("params") or {})


def _observation(candidate: dict[str, Any], factor: dict[str, Any]) -> FactorObservation | dict[str, Any] | None:
    factors = candidate.get("factors") or {}
    return factors.get(_key(factor)) or factors.get(str(factor.get("factor_id") or ""))


def _observation_value(observation: FactorObservation | dict[str, Any] | None) -> Any:
    if isinstance(observation, FactorObservation):
        return observation.value if observation.status == "available" else None
    if isinstance(observation, dict):
        return observation.get("value") if observation.get("status", "available") == "available" else None
    return None


def _missing_reason(observation: FactorObservation | dict[str, Any] | None) -> str:
    if isinstance(observation, FactorObservation):
        return observation.missing_reason or "missing_source_field"
    if isinstance(observation, dict):
        return str(observation.get("missing_reason") or "missing_source_field")
    return "missing_source_field"


def _matches(value: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return value == expected
    if operator == "ne":
        return value != expected
    if operator == "gt":
        return value > expected
    if operator == "gte":
        return value >= expected
    if operator == "lt":
        return value < expected
    if operator == "lte":
        return value <= expected
    if operator == "between":
        return expected[0] <= value <= expected[1]
    if operator == "in":
        return value in expected
    if operator == "not_in":
        return value not in expected
    raise McpCoreError("validation", f"unsupported filter operator: {operator}")


def apply_filters(
    candidates: list[dict[str, Any]],
    filters: list[dict[str, Any]],
    *,
    missing_policy: str,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    decisions: dict[str, list[dict[str, Any]]] = {}
    survivors = []
    for candidate in candidates:
        code = str(candidate.get("code") or "")
        rows = []
        eligible = True
        for filter_rule in filters:
            factor = filter_rule["factor"]
            observation = _observation(candidate, factor)
            value = _observation_value(observation)
            if value is None:
                reason = _missing_reason(observation)
                if missing_policy == "fail":
                    raise McpCoreError(
                        "not_ready",
                        "required filter factor is missing",
                        {"code": code, "factor": factor, "missing_reason": reason},
                    )
                passed = False
            else:
                reason = None
                passed = _matches(value, filter_rule["operator"], filter_rule["value"])
            rows.append(
                {
                    "factor": deepcopy(factor),
                    "operator": filter_rule["operator"],
                    "expected": deepcopy(filter_rule["value"]),
                    "value": value,
                    "actual": value,
                    "passed": passed,
                    "outcome": "missing" if value is None else "pass" if passed else "fail",
                    "missing_reason": reason,
                }
            )
            if not passed:
                eligible = False
                break
        decisions[code] = rows
        if eligible:
            survivors.append(candidate)
    return survivors, decisions


def _quantile(sorted_values: list[float], proportion: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _percentiles(
    values: dict[str, float], *, direction: str, target: float | None
) -> tuple[dict[str, float], dict[str, float]]:
    raw_values = sorted(values.values())
    winsorize = len(raw_values) >= 20
    lower = _quantile(raw_values, 0.01) if winsorize else raw_values[0]
    upper = _quantile(raw_values, 0.99) if winsorize else raw_values[-1]
    winsorized = {code: min(max(value, lower), upper) for code, value in values.items()}
    merit = {}
    for code, value in winsorized.items():
        if direction == "lower":
            merit[code] = -value
        elif direction == "target":
            merit[code] = -round(abs(value - float(target)), 15)
        else:
            merit[code] = value
    ordered = sorted(merit.values())
    if len(ordered) == 1:
        percentiles = {code: 1.0 for code in merit}
    else:
        positions: dict[float, list[int]] = {}
        for index, value in enumerate(ordered):
            positions.setdefault(value, []).append(index)
        percentiles = {
            code: (sum(positions[value]) / len(positions[value])) / (len(ordered) - 1) for code, value in merit.items()
        }
    return percentiles, winsorized


def _avg_amount(candidate: dict[str, Any]) -> float:
    observation = _observation(candidate, {"factor_id": "avg_amount", "params": {}})
    return finite_number(_observation_value(observation)) or -math.inf


def rank_candidates(
    candidates: list[dict[str, Any]],
    *,
    rank: list[dict[str, Any]],
    sort: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sort:
        rule = sort[0]
        factor = rule["factor"]
        direction = rule["direction"]

        def sort_key(candidate):
            value = finite_number(_observation_value(_observation(candidate, factor)))
            missing = value is None
            directed = 0.0 if missing else (-value if direction == "desc" else value)
            return missing, directed, str(candidate.get("code") or "")

        output = []
        for index, candidate in enumerate(sorted(candidates, key=sort_key), 1):
            output.append(
                {**deepcopy(candidate), "rank": index, "score": None, "coverage": 1.0, "rank_contributions": []}
            )
        return output, {"type": "direct_sort", "factor": deepcopy(factor), "direction": direction}

    if not rank:
        raise McpCoreError("validation", "rank or sort is required")
    total_weight = sum(float(rule["weight"]) for rule in rank)
    weights = [float(rule["weight"]) / total_weight for rule in rank]
    working = list(candidates)
    for rule in rank:
        if rule.get("missing_policy") == "exclude":
            working = [
                candidate
                for candidate in working
                if _observation_value(_observation(candidate, rule["factor"])) is not None
            ]
        elif rule.get("missing_policy") == "fail":
            missing = [
                str(candidate.get("code") or "")
                for candidate in working
                if _observation_value(_observation(candidate, rule["factor"])) is None
            ]
            if missing:
                raise McpCoreError(
                    "not_ready",
                    "rank factor is missing",
                    {"factor": rule["factor"], "codes": missing[:20], "missing_count": len(missing)},
                )

    contributions: dict[str, list[dict[str, Any]]] = {str(row.get("code") or ""): [] for row in working}
    coverages = {str(row.get("code") or ""): 0.0 for row in working}
    first_percentiles: dict[str, float] = {}
    for rule_index, (rule, weight) in enumerate(zip(rank, weights, strict=True)):
        factor = rule["factor"]
        values = {}
        for candidate in working:
            code = str(candidate.get("code") or "")
            value = finite_number(_observation_value(_observation(candidate, factor)))
            if value is not None:
                values[code] = value
        percentiles, winsorized = (
            _percentiles(
                values,
                direction=str(rule.get("direction") or "higher"),
                target=finite_number(rule.get("target")),
            )
            if values
            else ({}, {})
        )
        for candidate in working:
            code = str(candidate.get("code") or "")
            observation = _observation(candidate, factor)
            raw_value = finite_number(_observation_value(observation))
            if raw_value is None:
                percentile = 0.5
                missing_reason = _missing_reason(observation)
            else:
                percentile = percentiles[code]
                missing_reason = None
                coverages[code] += weight
            if rule_index == 0:
                first_percentiles[code] = percentile
            contributions[code].append(
                {
                    "factor": deepcopy(factor),
                    "raw_value": raw_value,
                    "winsorized_value": winsorized.get(code),
                    "percentile": percentile,
                    "requested_weight": float(rule["weight"]),
                    "effective_weight": weight,
                    "contribution": percentile * weight * 100,
                    "missing_policy": rule.get("missing_policy", "exclude"),
                    "missing_reason": missing_reason,
                }
            )

    output = []
    for candidate in working:
        code = str(candidate.get("code") or "")
        items = contributions[code]
        output.append(
            {
                **deepcopy(candidate),
                "score": sum(item["contribution"] for item in items),
                "coverage": coverages[code],
                "rank_contributions": items,
            }
        )
    output.sort(
        key=lambda row: (
            -row["score"],
            -row["coverage"],
            -first_percentiles[str(row.get("code") or "")],
            -_avg_amount(row),
            str(row.get("code") or ""),
        )
    )
    for index, row in enumerate(output, 1):
        row["rank"] = index
    return output, {
        "type": "weighted_percentile",
        "winsorization": [0.01, 0.99] if len(working) >= 20 else None,
        "normalized_weights": weights,
        "tie_breakers": ["coverage", "first_rank_factor", "avg_amount", "code"],
    }
