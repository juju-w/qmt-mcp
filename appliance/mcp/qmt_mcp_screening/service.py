"""Screening orchestration and strict universe resolution."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from qmt_mcp_core.errors import McpCoreError

from .cache import FactorObservationCache, ScreenResultStore
from .catalog import FACTOR_VERSION, IMPLEMENTED_FACTORS, factor_definition
from .exposures import EXPOSURES, canonical_exposure, match_exposure
from .financial_factors import FinancialTimeline, TimelineError, calculate_financial_factor
from .market_factors import calculate_market_factor
from .models import FactorObservation, factor_ref_label
from .profiles import classify_stock_profiles, etf_profile_for
from .ranking import apply_filters, rank_candidates
from .validation import normalize_screen_request

FINANCIAL_FACTORS = frozenset(
    {
        "earnings_yield_ttm",
        "pb_mrq",
        "roe_ttm",
        "revenue_growth_yoy",
        "net_profit_growth_yoy",
        "gross_margin_ttm",
        "cfo_to_net_profit_ttm",
        "debt_to_assets",
        "asset_growth_yoy",
    }
)
FINANCIAL_MARKET_CAP_FACTORS = frozenset({"earnings_yield_ttm", "pb_mrq"})
HISTORICAL_CAPITAL_MARKET_FACTORS = frozenset({"float_market_cap", "total_market_cap", "turnover_rate"})
SHARE_FIELDS = (
    "float_shares",
    "FloatVolume",
    "float_volume",
    "circulating_shares",
    "total_shares",
    "TotalVolume",
    "total_volume",
    "shares",
)
SNAPSHOT_FACTORS = frozenset({"bid_ask_spread_bps", "premium_to_iopv", "abs_premium_to_iopv"})


class UniverseResolver:
    def __init__(
        self,
        *,
        cache_provider: Callable[[], dict[str, Any]],
        sector_provider: Callable[[str], list[str] | None],
        max_codes: int = 5000,
    ):
        self.cache_provider = cache_provider
        self.sector_provider = sector_provider
        self.max_codes = max_codes

    def resolve(self, *, asset_type: str, universe: dict[str, Any]) -> dict[str, Any]:
        cache = self.cache_provider() or {}
        records = [record for record in cache.get("records", []) if isinstance(record, dict)]
        by_code = {str(record.get("code") or ""): record for record in records if record.get("code")}
        kind = str(universe.get("kind") or "")
        values = list(dict.fromkeys(str(value).strip() for value in universe.get("values", []) if str(value).strip()))
        policy = str(universe.get("policy") or "require_complete")
        complete = not bool(cache.get("partial") or cache.get("uses_seed") and kind in {"market", "exposure"})
        provenance: list[dict[str, Any]] = []
        warnings: list[str] = []
        exposure_group = None
        resolved_name = str(universe.get("name") or "")

        if kind == "codes":
            selected = values
            complete = True
            provenance.append({"source": "caller-codes", "values": values[:20]})
        elif kind == "sector":
            selected = []
            for sector in values:
                members = self.sector_provider(sector)
                if members is None:
                    complete = False
                    warnings.append(f"sector membership unavailable: {sector}")
                    continue
                selected.extend(str(code) for code in members)
                provenance.append({"source": "xtdata-sector", "sector": sector})
            resolved_name = resolved_name or ", ".join(values)
        elif kind == "market":
            if values != ["a_share"] and values != ["all_etf"]:
                raise McpCoreError(
                    "validation",
                    "unsupported market universe",
                    {"values": values, "allowed": ["a_share", "all_etf"]},
                )
            if values == ["all_etf"]:
                selected = [code for code, record in by_code.items() if self._record_asset(record) == "etf"]
                provenance.append({"source": "instrument-cache", "type": "etf"})
                resolved_name = "All exchange-traded funds"
            else:
                selected = []
                for sector in ("沪深A股", "京市A股"):
                    members = self.sector_provider(sector)
                    if members is None:
                        complete = False
                        warnings.append(f"sector membership unavailable: {sector}")
                    else:
                        selected.extend(str(code) for code in members)
                        provenance.append({"source": "xtdata-sector", "sector": sector})
                resolved_name = "A shares"
        elif kind == "exposure":
            if len(values) != 1:
                raise McpCoreError("validation", "exposure universe requires exactly one value")
            exposure_group = canonical_exposure(values[0])
            selected = [code for code, record in by_code.items() if match_exposure(record, exposure_group)]
            resolved_name = EXPOSURES[exposure_group]["labels"]["zh-CN"]
            provenance.append({"source": "strict-exposure-alias", "exposure_group": exposure_group})
        else:
            raise McpCoreError(
                "validation",
                f"invalid universe kind: {kind}",
                {"allowed": ["codes", "sector", "market", "exposure"]},
            )

        selected = sorted(set(selected))
        selected = [code for code in selected if code in by_code and self._record_asset(by_code[code]) == asset_type]
        if len(selected) > self.max_codes:
            raise McpCoreError(
                "capacity",
                "resolved universe exceeds configured limit",
                {"resolved": len(selected), "max_universe_codes": self.max_codes},
            )
        if not selected:
            raise McpCoreError(
                "not_ready",
                "resolved universe is empty",
                {"kind": kind, "values": values, "guidance": "refresh the instrument cache or narrow exact inputs"},
            )
        if not complete:
            warnings.append("universe membership is partial or seed-backed")
            if policy == "require_complete":
                raise McpCoreError(
                    "not_ready",
                    "complete universe membership is unavailable",
                    {"kind": kind, "values": values, "warnings": warnings},
                )
        digest = hashlib.sha256("\n".join(selected).encode("utf-8")).hexdigest()
        return {
            "asset_type": asset_type,
            "requested": {
                "kind": kind,
                "values": values,
                "policy": policy,
                "include_suspended": bool(universe.get("include_suspended", False)),
            },
            "resolved_name": resolved_name,
            "exposure_group": exposure_group,
            "codes": selected,
            "member_count": len(selected),
            "membership_digest": f"sha256:{digest}",
            "complete": complete,
            "provenance": provenance,
            "warnings": list(dict.fromkeys(warnings)),
            "records": {code: by_code[code] for code in selected},
        }

    @staticmethod
    def _record_asset(record: dict[str, Any]) -> str:
        return "etf" if str(record.get("instrument_type") or "").lower() == "etf" else "stock"


def _factor_refs(request: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    seen = set()
    for item in [*request["filters"], *request["rank"], *request["sort"]]:
        factor = item["factor"]
        label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
        if label not in seen:
            refs.append(factor)
            seen.add(label)
    return refs


def _factor_id(rule: dict[str, Any]) -> str:
    return str(rule["factor"]["factor_id"])


def _bar_count(refs: list[dict[str, Any]]) -> int:
    required = 1
    for ref in refs:
        factor_id = ref["factor_id"]
        window = int((ref.get("params") or {}).get("window") or 0)
        if factor_id in {"return", "annualized_volatility", "amihud_illiquidity", "sector_relative_strength"}:
            required = max(required, window + 1)
        elif factor_id == "amount_ratio":
            required = max(required, window + 1)
        elif factor_id == "ma_alignment":
            required = max(required, 120)
        else:
            required = max(required, window)
    return min(max(required, 1), 260)


class ScreeningService:
    """Execute one bounded, read-only, point-in-time screening request."""

    def __init__(
        self,
        *,
        resolver: UniverseResolver,
        source: Any,
        factor_cache: FactorObservationCache | None = None,
        result_store: ScreenResultStore | None = None,
        limits: dict[str, int] | None = None,
    ):
        self.resolver = resolver
        self.source = source
        self.factor_cache = factor_cache or FactorObservationCache()
        self.result_store = result_store or ScreenResultStore()
        self.limits = {
            "max_universe_codes": resolver.max_codes,
            "max_factor_refs": 24,
            "max_results": 100,
            **(limits or {}),
        }

    def _profiles(self, asset_type: str, universe: dict[str, Any], requested: str) -> dict[str, str]:
        codes = universe["codes"]
        if asset_type == "stock":
            sector_members = {sector: self.resolver.sector_provider(sector) for sector in ("银行", "证券", "保险")}
            classified = classify_stock_profiles(codes, sector_members)
            if requested == "non_financial" and not classified["complete"]:
                raise McpCoreError(
                    "not_ready",
                    "stock profile classifier is incomplete",
                    {"missing_sectors": classified["missing_sectors"]},
                )
            return classified["profiles"]
        exposure = universe.get("exposure_group") or ""
        return {code: etf_profile_for(exposure, universe["records"][code].get("name", "")) for code in codes}

    def _check_capabilities(self, request: dict[str, Any]) -> list[str]:
        capabilities = set(getattr(self.source, "capabilities", ()))
        warnings = []
        hard_ids = {_factor_id(rule) for rule in request["filters"]}
        for rule in [*request["filters"], *request["rank"], *request["sort"]]:
            factor = rule["factor"]
            definition = factor_definition(factor["factor_id"])
            missing = sorted(set(definition.required_capabilities) - capabilities)
            if factor["factor_id"] not in IMPLEMENTED_FACTORS:
                missing.append("screening_implementation")
            if request["as_of"] and factor["factor_id"] in SNAPSHOT_FACTORS:
                missing.append("historical_snapshot")
            if (
                request["as_of"]
                and factor["factor_id"] in HISTORICAL_CAPITAL_MARKET_FACTORS
                and "financial_data" not in capabilities
            ):
                missing.append("financial_data")
            if not missing:
                continue
            policy = rule.get("missing_policy", request["rank_missing_policy"])
            if factor["factor_id"] in hard_ids or policy == "fail" or rule in request["sort"]:
                raise McpCoreError(
                    "capability",
                    f"required factor is unavailable: {factor['factor_id']}",
                    {
                        "factor": deepcopy(factor),
                        "missing_capabilities": sorted(set(missing)),
                        "repair_tools": self._repair_tools(set(missing)),
                        "guidance": "call qmt_factor_catalog and use an available factor, or prepare the local QMT data explicitly",
                    },
                )
            warnings.append(f"optional factor unavailable: {factor['factor_id']} ({', '.join(sorted(set(missing)))})")
        return warnings

    @staticmethod
    def _repair_tools(missing: set[str]) -> list[str]:
        tools = []
        if "daily_bars" in missing:
            tools.append("qmt_xtdata_download_history_batch")
        if "financial_data" in missing:
            tools.append("qmt_xtdata_download_financial_data")
        if missing.intersection({"etf_reference", "etf_iopv"}):
            tools.append("qmt_xtdata_download_etf_info")
        return tools

    def _cache_key(
        self,
        *,
        code: str,
        factor: dict[str, Any],
        context: Any,
        universe_digest: str,
    ) -> tuple:
        return (
            getattr(self.source, "broker_id", "default"),
            FACTOR_VERSION,
            code,
            context.as_of,
            context.price_adjustment,
            factor["factor_id"],
            tuple(sorted((factor.get("params") or {}).items())),
            universe_digest if factor["factor_id"] == "sector_relative_strength" else "",
        )

    def _put_observation(
        self,
        candidate: dict[str, Any],
        factor: dict[str, Any],
        observation: FactorObservation,
        *,
        context: Any,
        universe_digest: str,
    ) -> None:
        label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
        candidate["factors"][label] = observation
        self.factor_cache.put(
            self._cache_key(
                code=candidate["code"],
                factor=factor,
                context=context,
                universe_digest=universe_digest,
            ),
            observation,
            freshness=factor_definition(factor["factor_id"]).freshness,
        )

    def _missing_optional(
        self,
        candidate: dict[str, Any],
        factor: dict[str, Any],
        *,
        reason: str,
        context: Any,
        universe_digest: str,
    ) -> None:
        definition = factor_definition(factor["factor_id"])
        observation = FactorObservation.missing(
            code=candidate["code"],
            factor_id=factor["factor_id"],
            params=factor.get("params") or {},
            reason=reason,
            unit=definition.unit,
        )
        self._put_observation(candidate, factor, observation, context=context, universe_digest=universe_digest)

    @staticmethod
    def _apply_historical_capital(candidate: dict[str, Any], timeline: FinancialTimeline) -> None:
        for field in SHARE_FIELDS:
            candidate["instrument"].pop(field, None)
        capital = timeline.latest("Capital") or {}
        float_shares = capital.get("float_shares")
        total_shares = capital.get("total_shares")
        if float_shares is not None:
            candidate["instrument"]["float_shares"] = float_shares
        if total_shares is not None:
            candidate["instrument"]["total_shares"] = total_shares
        candidate["instrument"]["_capital_announcement"] = capital.get("announce_time")

    def screen(self, raw_request: dict[str, Any]) -> dict[str, Any]:
        request = normalize_screen_request(raw_request, limits=self.limits)
        source_error_offset = getattr(self.source, "error_count", len(getattr(self.source, "errors", ())))
        warnings = self._check_capabilities(request)
        unavailable_optional = {
            warning.split(": ", 1)[1].split(" ", 1)[0]
            for warning in warnings
            if warning.startswith("optional factor unavailable: ")
        }
        universe = self.resolver.resolve(asset_type=request["asset_type"], universe=request["universe"])
        requested_profile = request["stock_profile"] if request["asset_type"] == "stock" else request["etf_profile"]
        profiles = self._profiles(request["asset_type"], universe, requested_profile)
        refs = _factor_refs(request)
        available_refs = [ref for ref in refs if ref["factor_id"] not in unavailable_optional]
        financial_requested = any(ref["factor_id"] in FINANCIAL_FACTORS for ref in available_refs)
        if request["asset_type"] == "stock" and requested_profile == "auto" and financial_requested:
            requested_profile = "non_financial"
            request["stock_profile"] = requested_profile
        if (
            request["asset_type"] == "etf"
            and request["preset_id"] in {"etf_rotation", "etf_execution_quality"}
            and not universe.get("exposure_group")
        ):
            raise McpCoreError(
                "validation",
                "ETF comparison preset requires one resolved exposure group",
                {"preset_id": request["preset_id"], "guidance": "use universe.kind=exposure with a catalog alias"},
            )
        distinct_profiles = sorted(set(profiles.values()))
        if requested_profile == "auto" and len(distinct_profiles) > 1:
            raise McpCoreError(
                "validation",
                "auto profile resolved multiple incomparable groups",
                {
                    "profiles": distinct_profiles,
                    "guidance": f"set an explicit {request['asset_type']}_profile or narrow the universe",
                },
            )

        candidates = []
        profile_rejected: dict[str, dict[str, Any]] = {}
        for code in universe["codes"]:
            profile = profiles.get(code, "unknown")
            record = universe["records"][code]
            matches_profile = requested_profile in {"", "auto"} or profile == requested_profile
            active = request["universe"]["include_suspended"] or record.get("is_trading", True) is not False
            candidate = {
                "code": code,
                "name": str(record.get("name") or code),
                "asset_type": request["asset_type"],
                "profile": profile,
                "exposure_group": universe.get("exposure_group"),
                "warnings": [],
                "factors": {},
                "instrument": deepcopy(record),
            }
            if matches_profile and active:
                candidates.append(candidate)
            else:
                profile_rejected[code] = {
                    **candidate,
                    "reason": "profile_incompatible" if not matches_profile else "suspended",
                }

        if not candidates:
            raise McpCoreError(
                "not_ready",
                "no instruments remain after profile and trading-state gates",
                {"requested_profile": requested_profile, "profiles": profiles},
            )

        created_at = datetime.now(UTC)
        context = self.source.data_context(as_of=request["as_of"], captured_at=created_at.isoformat())
        by_code = {candidate["code"]: candidate for candidate in candidates}
        digest = universe["membership_digest"]

        cache_hits = 0
        cache_misses = 0
        for candidate in candidates:
            for factor in available_refs:
                cached = self.factor_cache.get(
                    self._cache_key(
                        code=candidate["code"],
                        factor=factor,
                        context=context,
                        universe_digest=digest,
                    )
                )
                if cached is None:
                    cache_misses += 1
                    continue
                label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
                candidate["factors"][label] = cached
                cache_hits += 1

        bar_refs = [ref for ref in available_refs if ref["factor_id"] not in FINANCIAL_FACTORS | SNAPSHOT_FACTORS]
        pending_bar_refs = [
            ref
            for ref in bar_refs
            if any(
                factor_ref_label(ref["factor_id"], ref.get("params") or {}) not in candidate["factors"]
                for candidate in candidates
            )
        ]
        count = _bar_count(pending_bar_refs)
        codes = [candidate["code"] for candidate in candidates]
        adjusted_refs = [
            ref for ref in pending_bar_refs if ref["factor_id"] not in {"float_market_cap", "total_market_cap"}
        ]
        adjusted = (
            self.source.daily_bars(
                codes,
                count=count,
                dividend_type="front_ratio",
                completed_through=context.market_session or context.as_of,
            )
            if adjusted_refs
            else {}
        )
        unadjusted_refs = [
            ref for ref in pending_bar_refs if ref["factor_id"] in {"float_market_cap", "total_market_cap"}
        ]
        historical_capital_refs = [
            ref for ref in pending_bar_refs if ref["factor_id"] in HISTORICAL_CAPITAL_MARKET_FACTORS
        ]
        capital_financial: dict[str, dict[str, tuple[dict[str, Any], ...]]] = {}
        if request["as_of"] and historical_capital_refs:
            capital_financial = self.source.financial_tables(codes, ["Capital"], end_time=context.as_of)
            for candidate in candidates:
                try:
                    capital_timeline = FinancialTimeline(
                        capital_financial.get(candidate["code"], {}),
                        as_of=context.as_of,
                    )
                except TimelineError:
                    for field in SHARE_FIELDS:
                        candidate["instrument"].pop(field, None)
                else:
                    self._apply_historical_capital(candidate, capital_timeline)
        unadjusted = (
            self.source.daily_bars(
                codes,
                count=max(1, count),
                dividend_type="none",
                completed_through=context.market_session or context.as_of,
            )
            if unadjusted_refs
            else {}
        )

        peer_values: dict[str, list[float]] = {}
        for ref in pending_bar_refs:
            if ref["factor_id"] != "sector_relative_strength":
                continue
            label = factor_ref_label("return", ref.get("params") or {})
            values = []
            for candidate in candidates:
                observation = calculate_market_factor(
                    code=candidate["code"],
                    factor_id="return",
                    params=ref.get("params") or {},
                    bars=list(adjusted.get(candidate["code"], ()))[:260],
                )
                if observation.status == "available":
                    values.append(observation.value)
            peer_values[label] = values

        for candidate in candidates:
            code = candidate["code"]
            for factor in pending_bar_refs:
                label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
                if label in candidate["factors"]:
                    continue
                factor_id = factor["factor_id"]
                rows = (
                    unadjusted.get(code, ())
                    if factor_id in {"float_market_cap", "total_market_cap"}
                    else adjusted.get(code, ())
                )
                peers = peer_values.get(factor_ref_label("return", factor.get("params") or {}))
                observation = calculate_market_factor(
                    code=code,
                    factor_id=factor_id,
                    params=factor.get("params") or {},
                    bars=list(rows)[-260:],
                    instrument=candidate["instrument"],
                    peer_returns=peers,
                    as_of=context.as_of,
                )
                capital_announcement = candidate["instrument"].get("_capital_announcement")
                if capital_announcement and factor_id in HISTORICAL_CAPITAL_MARKET_FACTORS:
                    observation = replace(observation, announcement_time=str(capital_announcement))
                self._put_observation(candidate, factor, observation, context=context, universe_digest=digest)

        cheap_filters = [
            rule for rule in request["filters"] if _factor_id(rule) not in FINANCIAL_FACTORS | SNAPSHOT_FACTORS
        ]
        cheap_survivors, _cheap_decisions = apply_filters(
            candidates, cheap_filters, missing_policy=request["filter_missing_policy"]
        )

        snapshots: dict[str, dict[str, Any]] = {}
        snapshot_refs = [ref for ref in available_refs if ref["factor_id"] in SNAPSHOT_FACTORS]
        snapshot_candidates = [
            candidate
            for candidate in cheap_survivors
            if any(
                factor_ref_label(ref["factor_id"], ref.get("params") or {}) not in candidate["factors"]
                for ref in snapshot_refs
            )
        ]
        if snapshot_refs and snapshot_candidates and not request["as_of"]:
            snapshots = self.source.snapshots(
                [candidate["code"] for candidate in snapshot_candidates],
                expected_session=context.market_session,
            )
            for candidate in snapshot_candidates:
                for factor in snapshot_refs:
                    label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
                    if label in candidate["factors"]:
                        continue
                    if factor["factor_id"] == "bid_ask_spread_bps":
                        observation = calculate_market_factor(
                            code=candidate["code"],
                            factor_id=factor["factor_id"],
                            params=factor.get("params") or {},
                            bars=[],
                            snapshot=snapshots.get(candidate["code"], {}),
                        )
                    else:
                        observation = FactorObservation.missing(
                            code=candidate["code"],
                            factor_id=factor["factor_id"],
                            params=factor.get("params") or {},
                            reason="unavailable_capability",
                            unit=factor_definition(factor["factor_id"]).unit,
                        )
                    self._put_observation(candidate, factor, observation, context=context, universe_digest=digest)
        elif snapshot_refs and snapshot_candidates:
            for candidate in snapshot_candidates:
                for factor in snapshot_refs:
                    self._missing_optional(
                        candidate,
                        factor,
                        reason="after_as_of",
                        context=context,
                        universe_digest=digest,
                    )

        prefinancial_filters = [rule for rule in request["filters"] if _factor_id(rule) not in FINANCIAL_FACTORS]
        prefinancial_survivors, _prefinancial_decisions = apply_filters(
            candidates, prefinancial_filters, missing_policy=request["filter_missing_policy"]
        )

        financial: dict[str, dict[str, tuple[dict[str, Any], ...]]] = {}
        financial_refs = [ref for ref in available_refs if ref["factor_id"] in FINANCIAL_FACTORS]
        financial_candidates = [
            candidate
            for candidate in prefinancial_survivors
            if any(
                factor_ref_label(ref["factor_id"], ref.get("params") or {}) not in candidate["factors"]
                for ref in financial_refs
            )
        ]
        market_cap_required = any(ref["factor_id"] in FINANCIAL_MARKET_CAP_FACTORS for ref in financial_refs)
        if financial_refs and financial_candidates:
            if market_cap_required and not unadjusted:
                financial_codes = [candidate["code"] for candidate in financial_candidates]
                unadjusted = self.source.daily_bars(
                    financial_codes,
                    count=1,
                    dividend_type="none",
                    completed_through=context.market_session or context.as_of,
                )
            financial = self.source.financial_tables(
                [candidate["code"] for candidate in financial_candidates],
                ["Balance", "Income", "CashFlow", "Capital"],
                end_time=context.as_of,
            )
            for candidate in financial_candidates:
                code = candidate["code"]
                try:
                    timeline = FinancialTimeline(financial.get(code, {}), as_of=context.as_of)
                except TimelineError:
                    for factor in financial_refs:
                        label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
                        if label in candidate["factors"]:
                            continue
                        self._missing_optional(
                            candidate,
                            factor,
                            reason="source_error",
                            context=context,
                            universe_digest=digest,
                        )
                    continue
                if request["as_of"] and market_cap_required:
                    self._apply_historical_capital(candidate, timeline)
                market_cap = None
                if market_cap_required:
                    cap_observation = calculate_market_factor(
                        code=code,
                        factor_id="total_market_cap",
                        params={},
                        bars=list(unadjusted.get(code, ()))[-260:],
                        instrument=candidate["instrument"],
                    )
                    market_cap = cap_observation.value if cap_observation.status == "available" else None
                for factor in financial_refs:
                    label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
                    if label in candidate["factors"]:
                        continue
                    observation = calculate_financial_factor(
                        code=code,
                        factor_id=factor["factor_id"],
                        timeline=timeline,
                        market_cap=market_cap,
                        stock_profile=candidate["profile"],
                    )
                    self._put_observation(candidate, factor, observation, context=context, universe_digest=digest)

        for candidate in candidates:
            for factor in refs:
                label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
                if label not in candidate["factors"]:
                    reason = (
                        "unavailable_capability"
                        if factor["factor_id"] in unavailable_optional
                        else "missing_source_field"
                    )
                    self._missing_optional(
                        candidate,
                        factor,
                        reason=reason,
                        context=context,
                        universe_digest=digest,
                    )

        survivors, filter_decisions = apply_filters(
            candidates, request["filters"], missing_policy=request["filter_missing_policy"]
        )
        ranked, rank_method = rank_candidates(survivors, rank=request["rank"], sort=request["sort"])
        returned = ranked[: request["limit"]]

        coverage_by_factor = {}
        rank_refs = [rule["factor"] for rule in request["rank"]]
        for factor in rank_refs:
            label = factor_ref_label(factor["factor_id"], factor.get("params") or {})
            available = sum(
                candidate["factors"].get(label) is not None and candidate["factors"][label].status == "available"
                for candidate in survivors
            )
            coverage_by_factor[label] = available / len(survivors) if survivors else 0.0

        public_results = [self._public_candidate(row) for row in returned]
        selected = {row["code"] for row in returned}
        ranked_codes = {row["code"] for row in ranked}
        archive_candidates = {}
        for code, candidate in {**profile_rejected, **by_code}.items():
            if code in selected:
                state = "selected"
            elif code in ranked_codes:
                state = "eligible_unselected"
            else:
                state = "rejected"
            ranked_row = next((row for row in ranked if row["code"] == code), None)
            archive_candidates[code] = self._archive_candidate(
                ranked_row or candidate,
                state=state,
                filter_decisions=filter_decisions.get(code, []),
                rejection_reason=candidate.get("reason"),
            )

        daily_dates = [
            str(row.get("time") or "")
            for rows in [*adjusted.values(), *unadjusted.values()]
            for row in rows
            if isinstance(row, dict) and row.get("time")
        ]
        cached_daily_dates = [
            observation.data_as_of
            for candidate in candidates
            for observation in candidate["factors"].values()
            if isinstance(observation, FactorObservation)
            and observation.data_as_of
            and factor_definition(observation.factor_id).freshness == "completed_daily"
        ]
        quote_times = [str(row.get("time") or "") for row in snapshots.values() if row.get("time")]
        announcements = [
            observation.announcement_time
            for candidate in candidates
            for observation in candidate["factors"].values()
            if isinstance(observation, FactorObservation) and observation.announcement_time
        ]
        sources = [
            {
                "name": "instrument-cache",
                "state": "complete" if universe["complete"] else "partial",
                "as_of": None,
            },
        ]
        if bar_refs or market_cap_required:
            sources.append(
                {
                    "name": "xtdata-daily-bars",
                    "state": "read" if daily_dates else "cache",
                    "as_of": max([*daily_dates, *cached_daily_dates], default=None),
                }
            )
        if snapshot_refs:
            sources.append(
                {
                    "name": "xtdata-snapshot",
                    "state": "read" if snapshots else "cache",
                    "as_of": max(quote_times, default=None),
                }
            )
        if financial_refs or capital_financial:
            sources.append(
                {
                    "name": "xtdata-announced-financial",
                    "state": "read" if financial or capital_financial else "cache",
                    "as_of": max(announcements, default=None),
                }
            )
        current_source_errors = getattr(self.source, "error_count", len(getattr(self.source, "errors", ())))
        new_source_error_count = max(0, current_source_errors - source_error_offset)
        if new_source_error_count:
            warnings.append(
                f"{new_source_error_count} bounded source batch error(s); inspect candidate missing reasons"
            )
        context = replace(context, sources=tuple(sources))

        expires_at = created_at + timedelta(seconds=self.result_store.ttl_seconds)
        archive = {
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "normalized_request": deepcopy(request),
            "data_context": context.to_dict(),
            "universe": self._public_universe(universe),
            "candidates": archive_candidates,
        }
        screen_id = self.result_store.put(archive)
        rejected_codes = set(universe["codes"]) - ranked_codes
        return {
            "ok": True,
            "screen_id": screen_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "request": deepcopy(raw_request),
            "normalized_request": deepcopy(request),
            "data_context": context.to_dict(),
            "universe": self._public_universe(universe),
            "stage_counts": {
                "resolved": len(universe["codes"]),
                "data_eligible": len(candidates),
                "passed_filters": len(survivors),
                "ranked": len(ranked),
                "returned": len(public_results),
            },
            "coverage": {
                "overall": sum(row["coverage"] for row in ranked) / len(ranked) if ranked else 0.0,
                "by_factor": coverage_by_factor,
            },
            "cache": {"factor_hits": cache_hits, "factor_misses": cache_misses},
            "rank_method": rank_method,
            "results": public_results,
            "rejected_summary": {"total": len(rejected_codes), "by_reason": self._rejected_reasons(archive_candidates)},
            "warnings": list(dict.fromkeys([*universe["warnings"], *warnings])),
            "next_tools": ["qmt_explain_screen_result", "qmt_xtdata_snapshot", "qmt_xtdata_kline_chart"],
        }

    def explain(self, screen_id: str, code: str, *, locale: str = "zh-CN") -> dict[str, Any]:
        if not str(screen_id).startswith("scr_"):
            raise McpCoreError(
                "not_found",
                "screen_id is unknown or expired",
                {"screen_id": screen_id, "guidance": "rerun qmt_screen_instruments and use its new screen_id"},
            )
        captured = self.result_store.get(str(screen_id))
        if captured is None:
            raise McpCoreError(
                "not_found",
                "screen_id is unknown or expired",
                {"screen_id": screen_id, "guidance": "rerun qmt_screen_instruments and use its new screen_id"},
            )
        normalized_code = str(code or "").strip().upper()
        candidate = (captured.get("candidates") or {}).get(normalized_code)
        if candidate is None:
            raise McpCoreError(
                "not_found",
                "code is not part of the captured screen",
                {
                    "screen_id": screen_id,
                    "code": normalized_code,
                    "guidance": "use a code from the exact resolved universe or run a new screen",
                },
            )
        state = str(candidate.get("state") or "rejected")
        selected = state == "selected"
        eligible = state in {"selected", "eligible_unselected"}
        if locale.lower().startswith("zh"):
            summary = (
                f"{normalized_code} 在本次已捕获筛选中的状态为 {state}，"
                f"排名为 {candidate.get('rank')}，覆盖率为 {candidate.get('coverage', 0):.2f}。"
            )
        else:
            summary = (
                f"{normalized_code} was {state} in this captured screen, with rank {candidate.get('rank')} "
                f"and coverage {candidate.get('coverage', 0):.2f}."
            )
        return {
            "ok": True,
            "screen_id": screen_id,
            "created_at": captured.get("created_at"),
            "expires_at": captured.get("expires_at"),
            **deepcopy(candidate),
            "selected": selected,
            "eligible": eligible,
            "summary": summary,
            "data_context": deepcopy(captured.get("data_context", {})),
            "universe": deepcopy(captured.get("universe", {})),
            "factor_version": (captured.get("data_context") or {}).get("factor_version", FACTOR_VERSION),
            "next_tools": ["qmt_xtdata_snapshot", "qmt_xtdata_kline_chart"],
        }

    @staticmethod
    def _public_universe(universe: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(universe[key])
            for key in (
                "resolved_name",
                "exposure_group",
                "complete",
                "member_count",
                "membership_digest",
                "provenance",
                "warnings",
            )
        }

    @staticmethod
    def _public_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        contributions = candidate.get("rank_contributions", [])
        key_factors = []
        for contribution in sorted(contributions, key=lambda item: item["contribution"], reverse=True)[:2]:
            observation = candidate["factors"].get(
                factor_ref_label(contribution["factor"]["factor_id"], contribution["factor"].get("params") or {})
            )
            payload = observation.to_dict() if isinstance(observation, FactorObservation) else {}
            key_factors.append(
                {
                    "factor": deepcopy(contribution["factor"]),
                    "status": payload.get("status", "missing"),
                    "value": contribution["raw_value"],
                    "unit": payload.get("unit"),
                    "percentile": contribution["percentile"],
                    "effective_weight": contribution["effective_weight"],
                    "contribution": contribution["contribution"],
                    "data_as_of": payload.get("data_as_of"),
                    "missing_reason": contribution.get("missing_reason"),
                }
            )
        return {
            "rank": candidate.get("rank"),
            "code": candidate["code"],
            "name": candidate["name"],
            "asset_type": candidate["asset_type"],
            "profile": candidate["profile"],
            "exposure_group": candidate.get("exposure_group"),
            "score": candidate.get("score"),
            "coverage": candidate.get("coverage", 1.0),
            "key_factors": key_factors,
            "warnings": list(candidate.get("warnings", [])),
        }

    @staticmethod
    def _archive_candidate(
        candidate: dict[str, Any],
        *,
        state: str,
        filter_decisions: list[dict[str, Any]],
        rejection_reason: str | None,
    ) -> dict[str, Any]:
        factors = {
            label: observation.to_dict() if isinstance(observation, FactorObservation) else deepcopy(observation)
            for label, observation in (candidate.get("factors") or {}).items()
        }
        return {
            "code": candidate["code"],
            "name": candidate["name"],
            "asset_type": candidate["asset_type"],
            "profile": candidate["profile"],
            "exposure_group": candidate.get("exposure_group"),
            "state": state,
            "rank": candidate.get("rank"),
            "score": candidate.get("score"),
            "coverage": candidate.get("coverage", 0.0),
            "filter_decisions": deepcopy(filter_decisions),
            "rank_contributions": deepcopy(candidate.get("rank_contributions", [])),
            "factors": factors,
            "rejection_reason": rejection_reason,
            "warnings": list(candidate.get("warnings", [])),
        }

    @staticmethod
    def _rejected_reasons(candidates: dict[str, dict[str, Any]]) -> dict[str, int]:
        reasons: dict[str, int] = {}
        for candidate in candidates.values():
            if candidate["state"] != "rejected":
                continue
            reason = candidate.get("rejection_reason")
            if not reason:
                failed = next((row for row in candidate["filter_decisions"] if not row["passed"]), None)
                reason = (
                    f"filter:{factor_ref_label(failed['factor']['factor_id'], failed['factor'].get('params') or {})}"
                    if failed
                    else "rank_missing"
                )
            reasons[reason] = reasons.get(reason, 0) + 1
        return reasons
