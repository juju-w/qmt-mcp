"""Dependency-light screening contracts and immutable observations."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Any

if sys.version_info >= (3, 12):  # noqa: UP036 - Windows release remains Python 3.11
    from typing import NotRequired, TypedDict
else:  # pragma: no cover - Windows launcher runtime
    from typing_extensions import NotRequired, TypedDict  # noqa: UP035


ASSET_TYPES = frozenset({"stock", "etf"})
STOCK_PROFILES = frozenset({"auto", "non_financial", "bank", "broker", "insurer"})
ETF_PROFILES = frozenset(
    {
        "auto",
        "broad_market_equity",
        "sector_theme_equity",
        "strategy_equity",
        "cross_border_equity",
        "bond",
        "commodity",
        "money_market",
    }
)
OBSERVATION_STATES = frozenset({"available", "missing", "stale", "not_applicable"})
MISSING_REASONS = frozenset(
    {
        "insufficient_history",
        "missing_source_field",
        "unavailable_capability",
        "permission_denied",
        "stale_snapshot",
        "one_sided_quote",
        "suspended",
        "non_comparable_denominator",
        "profile_incompatible",
        "exposure_unresolved",
        "after_as_of",
        "source_error",
        "invalid_source_value",
    }
)


class FactorRefInput(TypedDict):
    factor_id: str
    params: NotRequired[dict[str, Any]]


class UniverseInput(TypedDict):
    kind: str
    values: list[str]
    name: NotRequired[str]
    policy: NotRequired[str]
    include_suspended: NotRequired[bool]


class FilterInput(TypedDict):
    factor: FactorRefInput
    operator: str
    value: Any


class RankInput(TypedDict):
    factor: FactorRefInput
    weight: float
    direction: NotRequired[str]
    target: NotRequired[float | None]
    missing_policy: NotRequired[str]


class SortInput(TypedDict):
    factor: FactorRefInput
    direction: str
    missing_last: NotRequired[bool]


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def canonical_factor_ref(factor_id: str, params: dict[str, Any] | None = None) -> tuple[str, tuple]:
    return str(factor_id), _freeze(params or {})


def factor_ref_label(factor_id: str, params: dict[str, Any] | None = None) -> str:
    values = params or {}
    if not values:
        return factor_id
    rendered = ",".join(f"{key}={values[key]}" for key in sorted(values))
    return f"{factor_id}({rendered})"


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


@dataclass(frozen=True)
class FactorDefinition:
    factor_id: str
    labels: dict[str, str]
    descriptions: dict[str, str]
    asset_types: tuple[str, ...]
    profiles: tuple[str, ...]
    value_type: str
    unit: str
    domain: dict[str, Any]
    operators: tuple[str, ...]
    rank_direction: str
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_class: str = "derived"
    freshness: str = "completed_daily"
    point_in_time: bool = True
    adjustment: str | None = None
    nullable: bool = True
    required_capabilities: tuple[str, ...] = ()
    formula_summary: str = ""
    presets: tuple[str, ...] = ()

    def to_dict(self, *, locale: str = "zh-CN") -> dict[str, Any]:
        language = locale if locale in self.labels else "en"
        return {
            "factor_id": self.factor_id,
            "label": self.labels.get(language, self.factor_id),
            "description": self.descriptions.get(language, self.descriptions.get("en", "")),
            "asset_types": list(self.asset_types),
            "profiles": list(self.profiles),
            "value_type": self.value_type,
            "unit": self.unit,
            "domain": dict(self.domain),
            "operators": list(self.operators),
            "rank_direction": self.rank_direction,
            "parameters": {key: dict(value) for key, value in self.parameters.items()},
            "source_class": self.source_class,
            "freshness": self.freshness,
            "point_in_time": self.point_in_time,
            "adjustment": self.adjustment,
            "nullable": self.nullable,
            "required_capabilities": list(self.required_capabilities),
            "formula_summary": self.formula_summary,
            "presets": list(self.presets),
        }


@dataclass(frozen=True)
class FactorObservation:
    code: str
    factor_id: str
    params: dict[str, Any]
    status: str
    value: Any
    unit: str
    data_as_of: str = ""
    source: str = ""
    adjustment: str | None = None
    announcement_time: str | None = None
    missing_reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def available(
        cls,
        *,
        code: str,
        factor_id: str,
        params: dict[str, Any],
        value: Any,
        unit: str,
        data_as_of: str = "",
        source: str = "",
        adjustment: str | None = None,
        announcement_time: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> FactorObservation:
        return cls(
            code=code,
            factor_id=factor_id,
            params=dict(params),
            status="available",
            value=value,
            unit=unit,
            data_as_of=data_as_of,
            source=source,
            adjustment=adjustment,
            announcement_time=announcement_time,
            details=dict(details or {}),
        )

    @classmethod
    def missing(
        cls,
        *,
        code: str,
        factor_id: str,
        params: dict[str, Any],
        reason: str,
        unit: str,
        status: str = "missing",
        data_as_of: str = "",
        source: str = "",
        details: dict[str, Any] | None = None,
    ) -> FactorObservation:
        return cls(
            code=code,
            factor_id=factor_id,
            params=dict(params),
            status=status,
            value=None,
            unit=unit,
            data_as_of=data_as_of,
            source=source,
            missing_reason=reason,
            details=dict(details or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "factor": {"factor_id": self.factor_id, "params": dict(self.params)},
            "status": self.status,
            "value": self.value,
            "unit": self.unit,
            "data_as_of": self.data_as_of or None,
            "source": self.source,
            "adjustment": self.adjustment,
            "announcement_time": self.announcement_time,
            "missing_reason": self.missing_reason,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class DataContext:
    captured_at: str
    as_of: str
    market_session: str
    price_adjustment: str
    factor_version: str
    broker_id: str
    sources: tuple[dict[str, Any], ...] = ()

    def to_dict(self, *, include_broker_id: bool = False) -> dict[str, Any]:
        payload = {
            "captured_at": self.captured_at,
            "as_of": self.as_of,
            "market_session": self.market_session or None,
            "price_adjustment": self.price_adjustment,
            "factor_version": self.factor_version,
            "sources": [dict(source) for source in self.sources],
        }
        if include_broker_id:
            payload["broker_id"] = self.broker_id
        return payload
