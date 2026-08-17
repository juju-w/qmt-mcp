"""Screen request normalization and fail-fast domain validation."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

from qmt_mcp_core.errors import McpCoreError

from .catalog import PROFILES, factor_definition
from .models import ASSET_TYPES
from .presets import expand_preset

UNIVERSE_KINDS = frozenset({"codes", "sector", "market", "exposure"})
MISSING_POLICIES = frozenset({"exclude", "neutral", "fail"})
DATE_RE = re.compile(r"^$|^[0-9]{8}$")


def _validation(message: str, **details):
    raise McpCoreError("validation", message, details)


def _normalize_params(definition, raw: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(raw or {})
    unknown = sorted(set(values) - set(definition.parameters))
    if unknown:
        _validation(
            f"invalid parameters for {definition.factor_id}",
            factor_id=definition.factor_id,
            invalid=unknown,
            valid_parameters=sorted(definition.parameters),
        )
    normalized = {}
    for name, rule in definition.parameters.items():
        value = values.get(name, rule.get("default"))
        if rule.get("type") == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            _validation(f"{definition.factor_id}.{name} must be an integer", allowed=rule.get("allowed", []))
        allowed = rule.get("allowed")
        if allowed is not None and value not in allowed:
            _validation(
                f"invalid {definition.factor_id}.{name}: {value}",
                factor_id=definition.factor_id,
                parameter=name,
                allowed=allowed,
            )
        normalized[name] = value
    return normalized


def normalize_factor_ref(raw: dict[str, Any], *, asset_type: str, profile: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        _validation("factor must be an object")
    factor_id = str(raw.get("factor_id") or "")
    definition = factor_definition(factor_id)
    if asset_type not in definition.asset_types:
        _validation(
            f"factor {factor_id} is not valid for {asset_type}",
            factor_id=factor_id,
            asset_types=list(definition.asset_types),
        )
    if profile not in {"", "auto"} and definition.profiles and profile not in definition.profiles:
        _validation(
            f"factor {factor_id} is incompatible with profile {profile}",
            factor_id=factor_id,
            profile=profile,
            compatible_profiles=list(definition.profiles),
        )
    return {"factor_id": factor_id, "params": _normalize_params(definition, raw.get("params"))}


def _numeric(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        _validation(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError):
        _validation(f"{field} must be numeric")
    if not math.isfinite(result):
        _validation(f"{field} must be finite")
    return result


def _validate_domain(definition, value: float) -> None:
    minimum = definition.domain.get("minimum")
    maximum = definition.domain.get("maximum")
    if minimum is not None and value < minimum:
        _validation(f"{definition.factor_id} value below valid domain", minimum=minimum, value=value)
    if maximum is not None and value > maximum:
        _validation(f"{definition.factor_id} value above valid domain", maximum=maximum, value=value)


def _normalize_filter(raw: dict[str, Any], *, asset_type: str, profile: str) -> dict[str, Any]:
    factor = normalize_factor_ref(raw.get("factor") or {}, asset_type=asset_type, profile=profile)
    definition = factor_definition(factor["factor_id"])
    operator = str(raw.get("operator") or "")
    if operator not in definition.operators:
        _validation(
            f"operator {operator} is invalid for {definition.factor_id}",
            factor_id=definition.factor_id,
            operator=operator,
            allowed=list(definition.operators),
        )
    value = raw.get("value")
    if operator == "between":
        if not isinstance(value, list) or len(value) != 2:
            _validation("between requires exactly two values")
        normalized_value = [_numeric(item, field="filter value") for item in value]
        if normalized_value[0] > normalized_value[1]:
            _validation("between values must be ordered")
        for item in normalized_value:
            _validate_domain(definition, item)
    elif operator in {"in", "not_in"}:
        if not isinstance(value, list) or not value or len(value) > 100:
            _validation(f"{operator} requires 1-100 values")
        normalized_value = list(value)
    elif definition.value_type == "number":
        normalized_value = _numeric(value, field="filter value")
        _validate_domain(definition, normalized_value)
    elif definition.value_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            _validation("filter value must be an integer")
        _validate_domain(definition, float(value))
        normalized_value = value
    elif definition.value_type == "boolean":
        if not isinstance(value, bool):
            _validation("filter value must be boolean")
        normalized_value = value
    else:
        allowed = definition.domain.get("values", [])
        if value not in allowed:
            _validation("invalid enum filter value", value=value, allowed=allowed)
        normalized_value = value
    return {"factor": factor, "operator": operator, "value": normalized_value}


def _normalize_rank(raw: dict[str, Any], *, asset_type: str, profile: str, default_missing: str) -> dict[str, Any]:
    factor = normalize_factor_ref(raw.get("factor") or {}, asset_type=asset_type, profile=profile)
    definition = factor_definition(factor["factor_id"])
    weight = _numeric(raw.get("weight"), field="rank weight")
    if not 0 < weight <= 1:
        _validation("rank weight must be greater than zero and at most one", weight=weight)
    direction = str(raw.get("direction") or definition.rank_direction)
    if direction not in {"higher", "lower", "target"}:
        _validation("invalid rank direction", direction=direction, allowed=["higher", "lower", "target"])
    target = raw.get("target")
    if direction == "target":
        target = _numeric(target, field="rank target")
    policy = str(raw.get("missing_policy") or default_missing)
    if policy not in MISSING_POLICIES:
        _validation("invalid rank missing policy", policy=policy, allowed=sorted(MISSING_POLICIES))
    return {
        "factor": factor,
        "weight": weight,
        "direction": direction,
        "target": target if direction == "target" else None,
        "missing_policy": policy,
    }


def _normalize_sort(raw: dict[str, Any], *, asset_type: str, profile: str) -> dict[str, Any]:
    factor = normalize_factor_ref(raw.get("factor") or {}, asset_type=asset_type, profile=profile)
    direction = str(raw.get("direction") or "")
    if direction not in {"asc", "desc"}:
        _validation("invalid sort direction", direction=direction, allowed=["asc", "desc"])
    if raw.get("missing_last", True) is not True:
        _validation("missing_last must be true in screening v1")
    return {"factor": factor, "direction": direction, "missing_last": True}


def normalize_screen_request(raw: dict[str, Any], *, limits: dict[str, int] | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        _validation("screen request must be an object")
    bounds = {"max_universe_codes": 5000, "max_factor_refs": 24, "max_results": 100, **(limits or {})}
    asset_type = str(raw.get("asset_type") or "")
    if asset_type not in ASSET_TYPES:
        _validation("invalid asset_type", asset_type=asset_type, allowed=sorted(ASSET_TYPES))
    stock_profile = str(raw.get("stock_profile") or "auto")
    etf_profile = str(raw.get("etf_profile") or "auto")
    profile = stock_profile if asset_type == "stock" else etf_profile
    if profile not in ({"auto"} | set(PROFILES[asset_type])):
        _validation(f"invalid {asset_type} profile", profile=profile, allowed=["auto", *PROFILES[asset_type]])
    if asset_type == "stock" and raw.get("etf_profile") not in {None, ""}:
        _validation("etf_profile is invalid for a stock screen")
    if asset_type == "etf" and raw.get("stock_profile") not in {None, ""}:
        _validation("stock_profile is invalid for an ETF screen")

    universe = deepcopy(raw.get("universe") or {})
    kind = str(universe.get("kind") or "")
    values = universe.get("values")
    if kind not in UNIVERSE_KINDS:
        _validation("invalid universe kind", kind=kind, allowed=sorted(UNIVERSE_KINDS))
    if not isinstance(values, list) or not values or any(not str(value).strip() for value in values):
        _validation("universe.values must be a non-empty string array")
    values = list(dict.fromkeys(str(value).strip() for value in values))
    if kind == "codes" and len(values) > bounds["max_universe_codes"]:
        raise McpCoreError(
            "capacity",
            "universe code limit exceeded",
            {"requested": len(values), "max_universe_codes": bounds["max_universe_codes"]},
        )
    policy = str(universe.get("policy") or "require_complete")
    if policy not in {"require_complete", "allow_partial"}:
        _validation("invalid universe policy", policy=policy)
    normalized_universe = {
        "kind": kind,
        "values": values,
        "name": str(universe.get("name") or ""),
        "policy": policy,
        "include_suspended": bool(universe.get("include_suspended", False)),
    }

    as_of = str(raw.get("as_of") or "")
    if not DATE_RE.fullmatch(as_of):
        _validation("invalid as_of", as_of=as_of, expected="YYYYMMDD")
    filter_policy = str(raw.get("filter_missing_policy") or "exclude")
    rank_policy = str(raw.get("rank_missing_policy") or "exclude")
    if filter_policy not in {"exclude", "fail"}:
        _validation("invalid filter missing policy", policy=filter_policy, allowed=["exclude", "fail"])
    if rank_policy not in MISSING_POLICIES:
        _validation("invalid rank missing policy", policy=rank_policy, allowed=sorted(MISSING_POLICIES))

    preset_id = str(raw.get("preset_id") or "")
    preset = expand_preset(preset_id) if preset_id else {}
    if preset and preset["asset_type"] != asset_type:
        _validation("preset asset type mismatch", preset_id=preset_id, asset_type=preset["asset_type"])
    preset_profile = str(preset.get("stock_profile") or preset.get("etf_profile") or "")
    if profile == "auto" and preset_profile:
        profile = preset_profile
        if asset_type == "stock":
            stock_profile = profile
        else:
            etf_profile = profile

    filters = [
        _normalize_filter(item, asset_type=asset_type, profile=profile)
        for item in [*preset.get("filters", []), *(raw.get("filters") or [])]
    ]
    raw_rank = raw.get("rank") or preset.get("rank", [])
    raw_sort = raw.get("sort") or preset.get("sort", [])
    if raw_rank and raw_sort:
        _validation("rank and sort are mutually exclusive")
    rank = [
        _normalize_rank(item, asset_type=asset_type, profile=profile, default_missing=rank_policy) for item in raw_rank
    ]
    sort = [_normalize_sort(item, asset_type=asset_type, profile=profile) for item in raw_sort]
    if not rank and not sort:
        _validation("screen requires rank or sort rules", guidance="select a preset or provide rank/sort")
    factor_count = len(filters) + len(rank) + len(sort)
    if factor_count > bounds["max_factor_refs"]:
        raise McpCoreError(
            "capacity",
            "factor reference limit exceeded",
            {"requested": factor_count, "max_factor_refs": bounds["max_factor_refs"]},
        )
    limit = raw.get("limit", 20)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= bounds["max_results"]:
        _validation("limit out of bounds", minimum=1, maximum=bounds["max_results"])
    diagnostics = str(raw.get("diagnostics") or "summary")
    if diagnostics not in {"summary", "detailed"}:
        _validation("invalid diagnostics", allowed=["summary", "detailed"])
    return {
        "asset_type": asset_type,
        "stock_profile": stock_profile if asset_type == "stock" else "",
        "etf_profile": etf_profile if asset_type == "etf" else "",
        "universe": normalized_universe,
        "as_of": as_of,
        "preset_id": preset_id,
        "filters": filters,
        "rank": rank,
        "sort": sort,
        "filter_missing_policy": filter_policy,
        "rank_missing_policy": rank_policy,
        "limit": limit,
        "diagnostics": diagnostics,
    }
