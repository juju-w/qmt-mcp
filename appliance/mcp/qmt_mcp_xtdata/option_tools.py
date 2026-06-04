"""Option chain and VIX-input tools for 015."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from qmt_mcp_core.errors import McpCoreError, ok_envelope
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry

from .option_aliases import resolve_option_underlying
from .option_serializers import option_codes, option_detail_record, quote_midpoint
from .serializers import json_clean, snapshot_records
from .validation import validate_code, validate_codes, validate_date

OPTION_SECTORS_BY_MARKET = {
    "SH": ["上证期权"],
    "SZ": ["深证期权"],
    "IF": ["中金所"],
}


def _call_compatible(call_xtdata, names: list[str], *variants: tuple[Any, ...]) -> tuple[str, Any]:
    last: McpCoreError | None = None
    for name in names:
        for args in variants:
            try:
                return name, call_xtdata(name, *args)
            except McpCoreError as exc:
                last = exc
                if "unavailable" in exc.message or "TypeError" in exc.message or "takes" in exc.message:
                    continue
                raise
    raise last or McpCoreError("dependency", "no compatible xtdata option function is available")


def _today_yyyymmdd() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y%m%d")


def _validate_option_expiry(value: str) -> str:
    expiry = (value or "").strip()
    if not expiry:
        return ""
    if re.match(r"^[0-9]{6}$", expiry):
        return expiry
    validate_date(expiry, "expiry")
    return expiry


def _underlying_parts(underlying: str) -> tuple[str, str]:
    code, market = underlying.split(".", 1)
    if market == "SH" and code in {"000016", "000300", "000852", "000905"}:
        return code, "IF"
    return code, market


def _option_sector_names(underlying: str) -> list[str]:
    _, market = _underlying_parts(underlying)
    return OPTION_SECTORS_BY_MARKET.get(market, [f"{market}期权"])


def _detail_from_instrument(code: str, call_xtdata) -> dict[str, Any]:
    raw = call_xtdata("get_instrument_detail", code, True)
    detail = option_detail_record(code, raw)
    data = detail["raw_fields"]
    undl_code = data.get("OptUndlCode")
    undl_market = data.get("OptUndlMarket")
    if undl_code and undl_market:
        detail["underlying_code"] = f"{undl_code}.{undl_market}"
    return detail


def _detail_matches(
    detail: dict[str, Any],
    underlying: str,
    expiry: str = "",
    option_type: str = "",
    trade_date: str = "",
) -> bool:
    undl_code, undl_market = _underlying_parts(underlying)
    data = detail.get("raw_fields", {})
    text_fields = " ".join(
        str(data.get(name) or "")
        for name in ["ProductID", "ProductName", "InstrumentName", "OptUndlCode", "OptUndlCodeFull"]
    )
    if undl_code not in text_fields and str(data.get("OptUndlCode") or "") != undl_code:
        return False
    if undl_market in {"SH", "SZ"} and data.get("OptUndlMarket") and data.get("OptUndlMarket") != undl_market:
        return False

    expiry_date = str(detail.get("expiry_date") or "")
    if len(expiry) == 6 and not expiry_date.startswith(expiry):
        return False
    if len(expiry) == 8 and expiry_date != expiry:
        return False
    if option_type and detail.get("option_type") != option_type:
        return False
    if trade_date and len(trade_date) == 8:
        open_date = str(data.get("OpenDate") or "")
        create_date = str(data.get("CreateDate") or "")
        if create_date > "0":
            open_date = min(open_date or create_date, create_date)
        if open_date and open_date > trade_date:
            return False
        if expiry_date and expiry_date < trade_date:
            return False
    return True


def register_option_tools(mcp: Any, registry: ToolRegistry, health: HealthState, call_xtdata) -> None:
    def load_chain(
        underlying_code: str = "", family: str = "", expiry: str = "", option_type: str = "", limit: int = 200
    ):
        underlying = validate_code(resolve_option_underlying(underlying_code or family))
        expiry = _validate_option_expiry(expiry)
        if limit < 1 or limit > 1000:
            raise McpCoreError("validation", "limit out of bounds", {"min": 1, "max": 1000})
        normalized_type = {"C": "CALL", "P": "PUT", "CALL": "CALL", "PUT": "PUT"}.get(option_type.upper(), "")
        trade_date = expiry if len(expiry) == 8 else _today_yyyymmdd()
        dedate = expiry or trade_date

        source = "get_option_list"
        try:
            func, raw = _call_compatible(
                call_xtdata,
                ["get_option_list"],
                (underlying, dedate, normalized_type, True),
                (underlying, dedate, normalized_type),
                (underlying, dedate),
            )
            source = func
            codes = option_codes(raw)
        except McpCoreError:
            source = "sector-enumeration"
            codes = []
            for sector in _option_sector_names(underlying):
                try:
                    codes.extend(option_codes(call_xtdata("get_stock_list_in_sector", sector)))
                except McpCoreError:
                    continue

        details = []
        selected_codes = []
        for code in codes:
            try:
                detail = _detail_from_instrument(code, call_xtdata)
            except McpCoreError:
                try:
                    detail = option_detail_record(code, call_xtdata("get_option_detail_data", code))
                except McpCoreError:
                    continue
            if not _detail_matches(detail, underlying, expiry, normalized_type, trade_date):
                continue
            selected_codes.append(code)
            details.append(detail)
            if len(selected_codes) >= limit:
                break
        return {
            "source": source,
            "underlying_code": underlying,
            "dedate": dedate,
            "codes": selected_codes,
            "details": details,
            "truncated": len(selected_codes) >= limit,
        }

    def load_quotes(codes: list[str]) -> list[dict[str, Any]]:
        clean_codes = validate_codes(codes, max_codes=200)
        raw = call_xtdata("get_full_tick", clean_codes)
        quotes = snapshot_records(raw, clean_codes)
        for quote in quotes:
            quote["mid_price"] = quote_midpoint(quote)
        return quotes

    @registry.register(
        mcp,
        name="qmt_xtdata_option_underlyings",
        family="xtdata",
        description="List option underlyings when xtdata.get_option_undl_data is available.",
        audit_fields=["market"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xtdata_option_underlyings(market: str = "") -> dict[str, Any]:
        func, raw = _call_compatible(call_xtdata, ["get_option_undl_data"], (market,))
        return ok_envelope(source=func, underlyings=json_clean(raw) or [])

    @registry.register(
        mcp,
        name="qmt_xtdata_option_chain",
        family="xtdata",
        description="Return bounded option contract codes and details for one underlying/family.",
        audit_fields=["underlying_code", "family", "expiry", "option_type", "limit"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_option_chain(
        underlying_code: str = "",
        family: str = "",
        expiry: str = "",
        option_type: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        return ok_envelope(**load_chain(underlying_code, family, expiry, option_type, limit))

    @registry.register(
        mcp,
        name="qmt_xtdata_option_detail",
        family="xtdata",
        description="Return normalized option contract details for one or more option codes.",
        audit_fields=["codes"],
        worker_backed=True,
        timeout=20,
    )
    def qmt_xtdata_option_detail(codes: list[str]) -> dict[str, Any]:
        clean_codes = validate_codes(codes, max_codes=200)
        details = []
        for code in clean_codes:
            try:
                details.append(_detail_from_instrument(code, call_xtdata))
            except McpCoreError:
                details.append(option_detail_record(code, call_xtdata("get_option_detail_data", code)))
        return ok_envelope(details=details)

    @registry.register(
        mcp,
        name="qmt_xtdata_option_quotes",
        family="xtdata",
        description="Return current option quote snapshots with bid/ask midpoint.",
        audit_fields=["codes"],
        worker_backed=True,
        timeout=20,
    )
    def qmt_xtdata_option_quotes(codes: list[str]) -> dict[str, Any]:
        return ok_envelope(source="get_full_tick", quotes=load_quotes(codes))

    @registry.register(
        mcp,
        name="qmt_xtdata_option_iv",
        family="xtdata",
        description="Return realtime implied-volatility helper values when xtdata.get_option_iv is available.",
        audit_fields=["codes"],
        worker_backed=True,
        timeout=20,
    )
    def qmt_xtdata_option_iv(codes: list[str]) -> dict[str, Any]:
        clean_codes = validate_codes(codes, max_codes=200)
        rows = []
        for code in clean_codes:
            rows.append({"code": code, "iv": json_clean(call_xtdata("get_option_iv", code))})
        return ok_envelope(source="get_option_iv", rows=rows)

    @registry.register(
        mcp,
        name="qmt_xtdata_volatility_index_inputs",
        family="xtdata",
        description="Return normalized option-chain and quote inputs for an external VIX calculator; does not publish VIX.",
        audit_fields=["underlying_code", "family", "limit"],
        worker_backed=True,
        timeout=45,
    )
    def qmt_xtdata_volatility_index_inputs(
        underlying_code: str = "",
        family: str = "",
        expiry: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        chain = load_chain(underlying_code=underlying_code, family=family, expiry=expiry, limit=limit)
        codes = chain["codes"]
        quotes_raw = load_quotes(codes) if codes else []
        quotes = {quote["code"]: quote for quote in quotes_raw}
        rows = []
        for detail in chain["details"]:
            quote = quotes.get(detail["code"], {})
            rows.append(
                {
                    "expiry_date": detail.get("expiry_date"),
                    "strike": detail.get("exercise_price"),
                    "option_type": detail.get("option_type"),
                    "code": detail["code"],
                    "quote": quote,
                    "mid_price": quote.get("mid_price"),
                }
            )
        return ok_envelope(
            family=family or underlying_code,
            underlying_code=chain["underlying_code"],
            generated_from="xtdata-option-chain",
            rows=rows,
            diagnostics={"row_count": len(rows), "publishes_index_value": False},
        )

    health.update_family_tools("xtdata", registry.tool_names("xtdata"))
