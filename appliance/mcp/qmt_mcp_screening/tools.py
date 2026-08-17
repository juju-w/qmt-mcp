"""MCP registration for factor discovery, screening, and captured explanation."""

from __future__ import annotations

from typing import Any

from qmt_mcp_core.errors import ok_envelope
from qmt_mcp_core.registry import ToolRegistry

from .catalog import FACTOR_VERSION, PROFILES, catalog_for
from .exposures import exposure_groups
from .models import FilterInput, RankInput, SortInput, UniverseInput
from .presets import PRESETS, expand_preset
from .text import render_catalog, render_explanation, render_screen

CATALOG_DESCRIPTION = (
    "Discover valid server-owned screening factor IDs, parameters, ranges, profiles, presets, decimal ratio units, "
    "point-in-time/freshness semantics, and active-runtime availability before calling qmt_screen_instruments. Use this "
    "when translating natural-language "
    "conditions or after a validation error. Do not guess factor IDs, windows, profiles, or ETF exposure groups, and "
    "do not use ordinary-company fundamentals for ETFs or banks/brokers/insurers. This lists capabilities and next-tool "
    "guidance; it does not scan instruments or fetch bars, snapshots, financial tables, downloads, formulas, or trades."
)

SCREEN_DESCRIPTION = (
    "Screen one strict, comparable A-share stock or ETF universe with server-owned factors. Call qmt_factor_catalog "
    "first when factor IDs, windows, profiles, decimal units, presets, or exposure groups are uncertain. Instrument "
    "search may discover candidates, but fuzzy relevance is never a rank factor. Provide asset_type, one exact codes/"
    "sector/market/exposure universe, typed hard filters, and rank or sort rules. Stocks and ETFs never cross-rank; "
    "ordinary fundamentals never apply to banks/brokers/insurers; a best-ETF comparison requires one exposure group. "
    "Decimal ratios use 0.10 for 10 percent. Financial factors use announcement-time data, live execution factors "
    "require a fresh snapshot, and missing data "
    "is never zero. Large calls support MCP Tasks. Returns a captured screen_id, source dates, coverage, transparent "
    "contributions, and next tools. Explicitly prepare missing local data and rerun; this read-only tool never downloads "
    "data or places trades."
)

EXPLAIN_DESCRIPTION = (
    "Explain one exact code from a previously captured qmt_screen_instruments result. Requires its unexpired screen_id. "
    "Returns selected/rejected state, ordered filter decisions, raw values, percentiles, weights, contributions, "
    "coverage, source dates, missing/stale reasons, and warnings from that immutable screen. Do not use it for a code "
    "outside that screen or as a current quote. It does not fetch quotes, recompute factors, or change rank. If the ID "
    "expired, rerun qmt_screen_instruments rather than reconstructing a different result; use qmt_xtdata_snapshot or "
    "qmt_xtdata_kline_chart for current follow-up data."
)


def register_screening_tools(mcp: Any, registry: ToolRegistry, service: Any) -> None:
    @registry.register(
        mcp,
        name="qmt_factor_catalog",
        family="xtdata",
        description=CATALOG_DESCRIPTION,
        audit_fields=["asset_type", "profile", "locale", "include_unavailable"],
        worker_backed=False,
        timeout=10,
        text_renderer=render_catalog,
    )
    def qmt_factor_catalog(
        asset_type: str,
        profile: str = "",
        locale: str = "zh-CN",
        include_unavailable: bool = True,
    ) -> dict[str, Any]:
        language = "zh-CN" if locale.lower().startswith("zh") else "en"
        capabilities = set(getattr(service.source, "capabilities", ()))
        factors = catalog_for(
            asset_type,
            profile=profile,
            capabilities=capabilities,
            locale=language,
            include_unavailable=include_unavailable,
        )
        counts = {
            state: sum(item["availability"] == state for item in factors) for state in ("available", "unavailable")
        }
        presets = [
            expand_preset(preset_id) | {"preset_id": preset_id}
            for preset_id in PRESETS
            if PRESETS[preset_id]["asset_type"] == asset_type
        ]
        return ok_envelope(
            catalog_version=FACTOR_VERSION,
            asset_type=asset_type,
            profile=profile or "auto",
            locale=language,
            profiles=PROFILES.get(asset_type, []),
            presets=presets,
            exposure_groups=exposure_groups(language) if asset_type == "etf" else [],
            capabilities=sorted(capabilities),
            availability_counts=counts,
            factors=factors,
            limits=dict(service.limits),
            next_tools=["qmt_screen_instruments", "qmt_xtdata_search_instruments"],
        )

    @registry.register(
        mcp,
        name="qmt_screen_instruments",
        family="xtdata",
        description=SCREEN_DESCRIPTION,
        audit_fields=["asset_type", "stock_profile", "etf_profile", "universe", "as_of", "preset_id", "limit"],
        worker_backed=True,
        timeout=180,
        text_renderer=render_screen,
    )
    def qmt_screen_instruments(
        asset_type: str,
        universe: UniverseInput,
        stock_profile: str = "",
        etf_profile: str = "",
        as_of: str = "",
        preset_id: str = "",
        filters: list[FilterInput] | None = None,
        rank: list[RankInput] | None = None,
        sort: list[SortInput] | None = None,
        filter_missing_policy: str = "exclude",
        rank_missing_policy: str = "exclude",
        limit: int = 20,
        diagnostics: str = "summary",
    ) -> dict[str, Any]:
        request = {
            "asset_type": asset_type,
            "universe": universe,
            "as_of": as_of,
            "preset_id": preset_id,
            "filters": filters or [],
            "rank": rank or [],
            "sort": sort or [],
            "filter_missing_policy": filter_missing_policy,
            "rank_missing_policy": rank_missing_policy,
            "limit": limit,
            "diagnostics": diagnostics,
        }
        if stock_profile:
            request["stock_profile"] = stock_profile
        if etf_profile:
            request["etf_profile"] = etf_profile
        return service.screen(request)

    @registry.register(
        mcp,
        name="qmt_explain_screen_result",
        family="xtdata",
        description=EXPLAIN_DESCRIPTION,
        audit_fields=["screen_id", "code", "locale"],
        worker_backed=False,
        timeout=10,
        text_renderer=render_explanation,
    )
    def qmt_explain_screen_result(screen_id: str, code: str, locale: str = "zh-CN") -> dict[str, Any]:
        return service.explain(screen_id, code, locale=locale)
