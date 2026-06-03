"""Curated xtdata tool registration."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from qmt_mcp_core.errors import McpCoreError, ok_envelope
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry

from .search_cache import cache_state, refresh_cache, usable_cache_or_seed
from .search_index import resolve_from_results, search_records, search_sectors, validate_filters, validate_query
from .serializers import bars_rows, date_strings, json_clean, snapshot_records
from .validation import (
    MAX_DOWNLOAD_CODES,
    MAX_SECTOR_LIMIT,
    validate_code,
    validate_codes,
    validate_date,
    validate_dividend,
    validate_fields,
    validate_market,
    validate_period,
)

SEARCH_DESCRIPTION = (
    "Search cached xtdata instruments by natural-language name, code, alias, sector, pinyin initials, or theme before "
    "calling quote/history tools. Use this when the user says a phrase like 天岳, ZGWX, 恒生科技, 纳指, or a partial name "
    "that may not be a valid QMT code. Do not use this to fetch prices; after selecting a high-confidence candidate, "
    "call qmt_xtdata_snapshot, qmt_xtdata_bars, or qmt_xtdata_instrument_detail with the returned code. Default ranking "
    "is combined relevance + quote support + type preference + cached liquidity. Set rank_by=liquidity for ETF/theme "
    "searches where the most actively traded proxy is preferred. If confidence is low or results are ambiguous, ask "
    "the user to clarify instead of inventing a code."
)

RESOLVE_DESCRIPTION = (
    "Resolve a user phrase to the best instrument candidate plus bounded alternates and guidance. Use this when an AI "
    "needs one code to pass to qmt_xtdata_snapshot, qmt_xtdata_bars, or qmt_xtdata_instrument_detail but the user did "
    "not provide an exact QMT code. The tool reads the local instrument cache/seed list and returns resolved=false for "
    "low-confidence or ambiguous matches; in that case inspect alternates or ask the user instead of guessing. Prefer "
    "types can bias results toward ETF, index, or stock, and rank_by controls whether relevance, liquidity, or size is "
    "emphasized."
)

SECTOR_SEARCH_DESCRIPTION = (
    "Search cached xtdata sector names before narrowing instrument search. Use this when the user references a broad "
    "universe such as ETF, 港股, 指数, 行业, or a sector name fragment. Do not use this to fetch constituents directly; "
    "after selecting a sector, call qmt_xtdata_search_instruments with sectors=[...] or qmt_xtdata_sector_constituents "
    "when raw codes are needed."
)

REFRESH_SEARCH_CACHE_DESCRIPTION = (
    "Refresh the local instrument-search cache from xtdata sector and instrument-detail metadata. Use this after QMT/"
    "MiniQMT xtdata is ready, when cache status is missing/stale, or after changing the sector universe. This is a "
    "longer worker-backed maintenance tool; normal searches read the cache and should not refresh every time. Set "
    "refresh_metrics=true to populate bounded cached liquidity metrics for ranking ETF/theme candidates."
)

CACHE_STATUS_DESCRIPTION = (
    "Return instrument-search cache freshness, record count, sectors, and seed/stale status. Use this before expensive "
    "refreshes or when search results look incomplete. This does not call xtdata and is safe even when QMT is not ready."
)


def _xtdata():
    try:
        from xtquant import xtdata  # type: ignore
    except Exception as exc:
        raise McpCoreError("not_ready", "xtquant.xtdata is not importable from the broker pack") from exc
    return xtdata


def _call_xtdata(func_name: str, *args: Any, **kwargs: Any) -> Any:
    xtdata = _xtdata()
    func = getattr(xtdata, func_name, None)
    if func is None:
        raise McpCoreError("dependency", f"xtdata.{func_name} is unavailable in this xtquant version")
    try:
        return func(*args, **kwargs)
    except McpCoreError:
        raise
    except Exception as exc:
        raise McpCoreError("dependency", f"xtdata.{func_name} failed: {type(exc).__name__}: {exc}") from exc


def _call_first_available(names: list[str], *args: Any, **kwargs: Any) -> tuple[str, Any]:
    last_missing = None
    for name in names:
        try:
            return name, _call_xtdata(name, *args, **kwargs)
        except McpCoreError as exc:
            if exc.error_type != "dependency" or "unavailable" not in exc.message:
                raise
            last_missing = exc
    raise last_missing or McpCoreError("dependency", "no compatible xtdata function is available")


def _is_unsupported_function_error(exc: McpCoreError) -> bool:
    text = exc.message.lower()
    return exc.error_type == "dependency" and (
        "unavailable" in text
        or "function not realize" in text
        or "未支持此功能" in exc.message
        or "not supported" in text
        or "not realize" in text
    )


def _call_market_data(
    field_list: list[str],
    stock_list: list[str],
    period: str,
    start_time: str,
    end_time: str,
    count: int,
    dividend_type: str,
    fill_data: bool,
    enable_read_from_server: bool,
) -> tuple[str, Any]:
    last_error: McpCoreError | None = None
    full_args = (
        field_list,
        stock_list,
        period,
        start_time,
        end_time,
        count,
        dividend_type,
        fill_data,
        enable_read_from_server,
    )
    legacy_args = full_args[:-1]
    for name in ["get_market_data_ex", "get_market_data"]:
        for args in [full_args, legacy_args]:
            try:
                return name, _call_xtdata(name, *args)
            except McpCoreError as exc:
                last_error = exc
                if _is_unsupported_function_error(exc) or (
                    exc.error_type == "dependency"
                    and (
                        "unavailable" in exc.message
                        or "TypeError" in exc.message
                        or "takes" in exc.message
                        or "positional" in exc.message
                    )
                ):
                    continue
                raise
    raise last_error or McpCoreError("dependency", "no compatible xtdata market-data function is available")


def _search_cache_for_call(
    health: HealthState,
    refresh: str,
    sectors: list[str] | None = None,
    include_external: bool = False,
) -> dict[str, Any]:
    if refresh == "force":
        return refresh_cache(
            _call_xtdata,
            broker_id=health.config.broker_id,
            sectors=sectors,
            include_external=include_external,
            force=True,
        )
    if refresh == "stale":
        try:
            return refresh_cache(
                _call_xtdata,
                broker_id=health.config.broker_id,
                sectors=sectors,
                include_external=include_external,
                force=False,
            )
        except McpCoreError:
            return usable_cache_or_seed(health.config.broker_id)
    return usable_cache_or_seed(health.config.broker_id)


def register_xtdata_tools(mcp: FastMCP, registry: ToolRegistry, health: HealthState) -> None:
    health.xtdata = "not_ready"
    try:
        _xtdata()
        health.xtquant_import = "ok"
    except McpCoreError:
        health.xtquant_import = "error"
    health.set_family("xtdata", "not_ready", "xtdata tools registered; QMT login/readiness is checked per call", [])

    @registry.register(
        mcp,
        name="qmt_xtdata_snapshot",
        family="xtdata",
        description=(
            "Return the current quote snapshot (last/open/high/low/pre-close, bid/ask ladder, volume, amount) for up "
            "to 50 instruments. `codes` are full QMT codes like 600000.SH / 000001.SZ — if you only have a name or "
            "phrase, call qmt_xtdata_resolve_instrument first. Optional `fields` narrows the returned raw fields. "
            "Live data; requires QMT logged in (else trader/data not-ready)."
        ),
        audit_fields=["codes"],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_snapshot(codes: list[str], fields: list[str] | None = None) -> dict[str, Any]:
        clean_codes = validate_codes(codes)
        raw = _call_xtdata("get_full_tick", clean_codes)
        return ok_envelope(data=snapshot_records(raw, clean_codes))

    @registry.register(
        mcp,
        name="qmt_xtdata_download_history",
        family="xtdata",
        description=(
            "Download/cache historical data for ONE instrument into the local store so later qmt_xtdata_bars reads "
            "are complete. Args: `code` (one QMT code), `period` (tick/1m/5m/15m/30m/1h/1d/1w/1mon/...), optional "
            "`start_time`/`end_time` (YYYYMMDD or YYYYMMDDHHmmSS; empty = full range), `incremental`. Returns a status, "
            "NOT the bars — read them with qmt_xtdata_bars afterwards."
        ),
        audit_fields=["code", "period", "start_time", "end_time"],
        worker_backed=True,
        timeout=120,
    )
    def qmt_xtdata_download_history(
        code: str,
        period: str,
        start_time: str = "",
        end_time: str = "",
        incremental: bool = False,
    ) -> dict[str, Any]:
        clean_code = validate_code(code)
        clean_period = validate_period(period)
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        raw = _call_xtdata("download_history_data", clean_code, clean_period, start, end, incremental)
        return ok_envelope(
            code=clean_code,
            period=clean_period,
            start_time=start,
            end_time=end,
            downloaded=True,
            raw_result=json_clean(raw),
        )

    @registry.register(
        mcp,
        name="qmt_xtdata_download_history_batch",
        family="xtdata",
        description=(
            "Like qmt_xtdata_download_history but for up to 200 codes in one call (xtdata.download_history_data2). "
            "Args: `codes`, `period`, optional `start_time`/`end_time` (YYYYMMDD[HHmmSS]), `incremental`. Returns a "
            "status; read the bars with qmt_xtdata_bars."
        ),
        audit_fields=["codes", "period", "start_time", "end_time"],
        worker_backed=True,
        timeout=300,
    )
    def qmt_xtdata_download_history_batch(
        codes: list[str],
        period: str,
        start_time: str = "",
        end_time: str = "",
        incremental: bool | None = None,
    ) -> dict[str, Any]:
        clean_codes = validate_codes(codes, max_codes=MAX_DOWNLOAD_CODES)
        clean_period = validate_period(period)
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        raw = _call_xtdata("download_history_data2", clean_codes, clean_period, start, end, None, incremental)
        return ok_envelope(
            codes=clean_codes,
            period=clean_period,
            start_time=start,
            end_time=end,
            downloaded=bool(raw) if raw is not None else True,
            raw_result=json_clean(raw),
        )

    @registry.register(
        mcp,
        name="qmt_xtdata_bars",
        family="xtdata",
        description=(
            "Read OHLC bar rows for up to 50 codes. Args: `period` (default 1d; tick/1m/5m/15m/30m/1h/1d/1w/1mon/...), "
            "`fields` (default open/high/low/close/volume/amount), `start_time`/`end_time` (YYYYMMDD[HHmmSS], empty = "
            "all), `count` (-1 = all, else last N, max 10000), `dividend_type` (none/front/back/front_ratio/back_ratio). "
            "Reads cached/historical data — if a range is missing, call qmt_xtdata_download_history(_batch) first. Use "
            "qmt_xtdata_resolve_instrument / qmt_xtdata_search_instruments to get codes."
        ),
        audit_fields=["codes", "period", "start_time", "end_time", "count"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_bars(
        codes: list[str],
        period: str = "1d",
        fields: list[str] | None = None,
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
        enable_read_from_server: bool = True,
    ) -> dict[str, Any]:
        clean_codes = validate_codes(codes)
        clean_period = validate_period(period)
        clean_fields = validate_fields(fields)
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        div = validate_dividend(dividend_type)
        if count < -1 or count > 10000:
            raise McpCoreError("validation", "count out of bounds", {"min": -1, "max": 10000})
        func_name, raw = _call_market_data(
            clean_fields,
            clean_codes,
            clean_period,
            start,
            end,
            count,
            div,
            fill_data,
            enable_read_from_server,
        )
        return ok_envelope(period=clean_period, source=func_name, rows=bars_rows(raw, clean_codes, clean_fields))

    @registry.register(
        mcp,
        name="qmt_xtdata_instrument_detail",
        family="xtdata",
        description=(
            "Return metadata (name, type, exchange, listing/expiry, lot size, price limits, ...) for ONE QMT code. "
            "Set `complete=true` for the full field set. Use qmt_xtdata_resolve_instrument first if you only have a "
            "name or phrase rather than a code."
        ),
        audit_fields=["code"],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_instrument_detail(code: str, complete: bool = False) -> dict[str, Any]:
        clean_code = validate_code(code)
        raw = _call_xtdata("get_instrument_detail", clean_code, complete)
        data = json_clean(raw) or {}
        return ok_envelope(found=bool(data), instrument={"code": clean_code, "raw_fields": data})

    @registry.register(
        mcp,
        name="qmt_xtdata_sector_list",
        family="xtdata",
        description=(
            "List xtdata sector/category names (e.g. 沪深A股, 沪深ETF, 行业/概念板块), with an optional `filter` "
            "substring. For fuzzy/natural-language sector lookup use qmt_xtdata_search_sectors; use this to enumerate "
            "exact names, then pass one to qmt_xtdata_sector_constituents."
        ),
        audit_fields=["filter"],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_sector_list(filter: str = "") -> dict[str, Any]:  # noqa: A002
        raw = _call_xtdata("get_sector_list")
        sectors = json_clean(raw) or []
        if filter:
            sectors = [s for s in sectors if filter in str(s)]
        return ok_envelope(sectors=sectors)

    @registry.register(
        mcp,
        name="qmt_xtdata_sector_constituents",
        family="xtdata",
        description=(
            "List the instrument codes in one sector/category. Args: `sector` (an EXACT name from "
            "qmt_xtdata_sector_list / qmt_xtdata_search_sectors), `limit` (default 5000, max 10000). Returns codes "
            "only — fetch quotes/bars via qmt_xtdata_snapshot / qmt_xtdata_bars."
        ),
        audit_fields=["sector", "limit"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xtdata_sector_constituents(sector: str, limit: int = 5000, real_timetag: int | str = -1) -> dict[str, Any]:
        if not sector:
            raise McpCoreError("validation", "sector must not be empty")
        if limit < 1 or limit > MAX_SECTOR_LIMIT:
            raise McpCoreError("validation", "limit out of bounds", {"max": MAX_SECTOR_LIMIT})
        raw = _call_xtdata("get_stock_list_in_sector", sector, real_timetag)
        codes = (json_clean(raw) or [])[:limit]
        return ok_envelope(sector=sector, real_timetag=real_timetag, codes=codes)

    @registry.register(
        mcp,
        name="qmt_xtdata_index_weight",
        family="xtdata",
        description=(
            "Return constituent weights for ONE index code (e.g. 000300.SH) when the local xtdata index-weight cache "
            "is available. Args: `index_code` (QMT code), `limit`. Returns [{code, weight}]."
        ),
        audit_fields=["index_code", "limit"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xtdata_index_weight(index_code: str, limit: int = 5000) -> dict[str, Any]:
        clean_code = validate_code(index_code)
        if limit < 1 or limit > MAX_SECTOR_LIMIT:
            raise McpCoreError("validation", "limit out of bounds", {"max": MAX_SECTOR_LIMIT})
        raw = json_clean(_call_xtdata("get_index_weight", clean_code)) or {}
        if isinstance(raw, dict):
            items = list(raw.items())[:limit]
            weights = [{"code": str(code), "weight": weight} for code, weight in items]
        else:
            weights = []
        return ok_envelope(
            index_code=clean_code, weights=weights, raw_fields=raw if not isinstance(raw, dict) else None
        )

    @registry.register(
        mcp,
        name="qmt_xtdata_trading_dates",
        family="xtdata",
        description=(
            "Return trading dates for a market. Args: `market` (SH/SZ/BJ/IF/SF/DF/INE/GF/ZF), optional "
            "`start_time`/`end_time` (YYYYMMDD), `count` (-1 = all, else last N, max 10000). Returns normalized "
            "YYYYMMDD strings."
        ),
        audit_fields=["market", "start_time", "end_time"],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_trading_dates(
        market: str, start_time: str = "", end_time: str = "", count: int = -1
    ) -> dict[str, Any]:
        clean_market = validate_market(market)
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        if count < -1 or count > 10000:
            raise McpCoreError("validation", "count out of bounds", {"min": -1, "max": 10000})
        raw = _call_xtdata("get_trading_dates", clean_market, start, end, count)
        return ok_envelope(market=clean_market, dates=date_strings(raw), raw_dates=json_clean(raw) or [])

    @registry.register(
        mcp,
        name="qmt_xtdata_trading_calendar",
        family="xtdata",
        description=(
            "Return the trading calendar (normalized YYYYMMDD strings) for one `market` and optional "
            "`start_time`/`end_time` range; transparently falls back to trading-dates if the SDK lacks a calendar "
            "function."
        ),
        audit_fields=["market", "start_time", "end_time"],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_trading_calendar(market: str, start_time: str = "", end_time: str = "") -> dict[str, Any]:
        clean_market = validate_market(market)
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        try:
            _, raw = _call_first_available(["get_trading_calendar"], clean_market, start, end)
        except McpCoreError as exc:
            if not _is_unsupported_function_error(exc):
                raise
            raw = _call_xtdata("get_trading_dates", clean_market, start, end, -1)
        return ok_envelope(market=clean_market, dates=date_strings(raw), raw_dates=json_clean(raw) or [])

    @registry.register(
        mcp,
        name="qmt_xtdata_holidays",
        family="xtdata",
        description="Return the market holiday dates known to xtdata (normalized YYYYMMDD strings). No arguments.",
        audit_fields=[],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_holidays() -> dict[str, Any]:
        raw = _call_xtdata("get_holidays")
        return ok_envelope(dates=date_strings(raw))

    @registry.register(
        mcp,
        name="qmt_xtdata_search_instruments",
        family="xtdata",
        description=SEARCH_DESCRIPTION,
        audit_fields=["query", "limit", "rank_by"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_search_instruments(
        query: str,
        sectors: list[str] | None = None,
        markets: list[str] | None = None,
        types: list[str] | None = None,
        include_external: bool = False,
        limit: int = 20,
        refresh: str = "stale",
        rank_by: str = "combined",
        include_metrics: bool = True,
    ) -> dict[str, Any]:
        clean_query = validate_query(query, limit, refresh, rank_by)
        clean_sectors = validate_filters(sectors, "sectors")
        cache = _search_cache_for_call(health, refresh, clean_sectors or None, include_external)
        result = search_records(
            cache,
            clean_query,
            sectors=clean_sectors,
            markets=markets,
            types=types,
            include_external=include_external,
            limit=limit,
            rank_by=rank_by,
            include_metrics=include_metrics,
        )
        return ok_envelope(
            query=clean_query,
            cache=cache_state(cache),
            results=result["results"],
            truncated=result["truncated"],
        )

    @registry.register(
        mcp,
        name="qmt_xtdata_resolve_instrument",
        family="xtdata",
        description=RESOLVE_DESCRIPTION,
        audit_fields=["query", "limit", "rank_by"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_resolve_instrument(
        query: str,
        prefer_types: list[str] | None = None,
        include_external: bool = False,
        rank_by: str = "combined",
        min_score: int = 70,
        limit: int = 5,
        refresh: str = "stale",
    ) -> dict[str, Any]:
        clean_query = validate_query(query, limit, refresh, rank_by)
        if min_score < 1 or min_score > 100:
            raise McpCoreError("validation", "min_score out of bounds", {"min": 1, "max": 100})
        cache = _search_cache_for_call(health, refresh, None, include_external)
        result = search_records(
            cache,
            clean_query,
            include_external=include_external,
            limit=limit,
            rank_by=rank_by,
            include_metrics=True,
            prefer_types=prefer_types,
            min_score=1,
        )
        resolved = resolve_from_results(result["results"], min_score)
        return ok_envelope(
            query=clean_query,
            cache=cache_state(cache),
            truncated=result["truncated"],
            **resolved,
        )

    @registry.register(
        mcp,
        name="qmt_xtdata_search_sectors",
        family="xtdata",
        description=SECTOR_SEARCH_DESCRIPTION,
        audit_fields=["query", "limit"],
        worker_backed=True,
        timeout=20,
    )
    def qmt_xtdata_search_sectors(query: str, limit: int = 50, refresh: str = "stale") -> dict[str, Any]:
        clean_query = validate_query(query, limit, refresh, "relevance")
        cache = _search_cache_for_call(health, refresh, None, False)
        result = search_sectors(cache, clean_query, limit=limit)
        return ok_envelope(
            query=clean_query, cache=cache_state(cache), sectors=result["sectors"], truncated=result["truncated"]
        )

    @registry.register(
        mcp,
        name="qmt_xtdata_refresh_instrument_cache",
        family="xtdata",
        description=REFRESH_SEARCH_CACHE_DESCRIPTION,
        audit_fields=["sectors", "include_external", "force", "max_codes"],
        worker_backed=True,
        timeout=600,
    )
    def qmt_xtdata_refresh_instrument_cache(
        sectors: list[str] | None = None,
        include_external: bool = False,
        force: bool = False,
        max_codes: int = 20000,
        refresh_metrics: bool = True,
        metrics_count: int = 20,
        max_metric_codes: int = 500,
    ) -> dict[str, Any]:
        clean_sectors = validate_filters(sectors, "sectors", max_items=50)
        if metrics_count < 1 or metrics_count > 120:
            raise McpCoreError("validation", "metrics_count out of bounds", {"min": 1, "max": 120})
        if max_metric_codes < 0 or max_metric_codes > 5000:
            raise McpCoreError("validation", "max_metric_codes out of bounds", {"min": 0, "max": 5000})
        cache = refresh_cache(
            _call_xtdata,
            broker_id=health.config.broker_id,
            sectors=clean_sectors or None,
            include_external=include_external,
            force=force,
            max_codes=max_codes,
            refresh_metrics=refresh_metrics,
            metrics_count=metrics_count,
            max_metric_codes=max_metric_codes,
        )
        state = cache_state(cache)
        return ok_envelope(
            cache_path=state.get("cache_path"),
            record_count=state.get("record_count"),
            sector_count=state.get("sector_count"),
            source_sectors=state.get("source_sectors", []),
            partial=state.get("partial", False),
            updated_at=state.get("updated_at"),
            errors=cache.get("errors", [])[:20],
        )

    @registry.register(
        mcp,
        name="qmt_xtdata_instrument_cache_status",
        family="xtdata",
        description=CACHE_STATUS_DESCRIPTION,
        audit_fields=[],
        worker_backed=False,
        timeout=5,
    )
    def qmt_xtdata_instrument_cache_status() -> dict[str, Any]:
        cache = usable_cache_or_seed(health.config.broker_id)
        return ok_envelope(**cache_state(cache))

    health.xtdata = "not_ready"
    health.set_family(
        "xtdata",
        "not_ready",
        "xtdata tools registered; QMT login/readiness is checked per call",
        registry.tool_names("xtdata"),
    )
