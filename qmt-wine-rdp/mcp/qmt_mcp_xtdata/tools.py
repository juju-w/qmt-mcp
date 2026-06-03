"""Curated xtdata tool registration."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from qmt_mcp_core.errors import McpCoreError, ok_envelope
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry

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
    return (
        exc.error_type == "dependency"
        and (
            "unavailable" in text
            or "function not realize" in text
            or "未支持此功能" in exc.message
            or "not supported" in text
            or "not realize" in text
        )
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
                    exc.error_type == "dependency" and (
                        "unavailable" in exc.message
                        or "TypeError" in exc.message
                        or "takes" in exc.message
                        or "positional" in exc.message
                    )
                ):
                    continue
                raise
    raise last_error or McpCoreError("dependency", "no compatible xtdata market-data function is available")


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
        description="Return current full-tick/snapshot quote records for a bounded list of instrument codes.",
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
        description="Download/cache historical data for one instrument, period, and bounded date range.",
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
        description="Download/cache historical data for a bounded list of instruments using xtdata.download_history_data2.",
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
        description="Read cached/historical bar rows for bounded codes, period, fields, range, and dividend type.",
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
        description="Return instrument metadata for one QMT instrument code.",
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
        description="List available xtdata sector/category names with an optional substring filter.",
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
        description="List bounded instrument codes in one xtdata sector/category.",
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
        description="Return index constituent weights for one index code when local xtdata index weight cache is available.",
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
        return ok_envelope(index_code=clean_code, weights=weights, raw_fields=raw if not isinstance(raw, dict) else None)

    @registry.register(
        mcp,
        name="qmt_xtdata_trading_dates",
        family="xtdata",
        description="Return trading dates for a market and bounded date range.",
        audit_fields=["market", "start_time", "end_time"],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_trading_dates(market: str, start_time: str = "", end_time: str = "", count: int = -1) -> dict[str, Any]:
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
        description="Return normalized trading calendar date strings for one market and date range.",
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
        description="Return holiday dates known to xtdata.",
        audit_fields=[],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_holidays() -> dict[str, Any]:
        raw = _call_xtdata("get_holidays")
        return ok_envelope(dates=date_strings(raw))

    health.xtdata = "not_ready"
    health.set_family("xtdata", "not_ready", "xtdata tools registered; QMT login/readiness is checked per call", registry.tool_names("xtdata"))
