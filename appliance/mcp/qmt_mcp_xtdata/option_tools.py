"""Option chain and VIX-input tools for 015."""

from __future__ import annotations

from typing import Any

from qmt_mcp_core.errors import McpCoreError, ok_envelope
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry

from .option_aliases import resolve_option_underlying
from .option_serializers import option_codes, option_detail_record, quote_midpoint
from .serializers import json_clean, snapshot_records
from .validation import validate_code, validate_codes, validate_date


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


def register_option_tools(mcp: Any, registry: ToolRegistry, health: HealthState, call_xtdata) -> None:
    def load_chain(
        underlying_code: str = "", family: str = "", expiry: str = "", option_type: str = "", limit: int = 200
    ):
        underlying = validate_code(resolve_option_underlying(underlying_code or family))
        if expiry:
            validate_date(expiry, "expiry")
        if limit < 1 or limit > 1000:
            raise McpCoreError("validation", "limit out of bounds", {"min": 1, "max": 1000})
        func, raw = _call_compatible(
            call_xtdata,
            ["get_option_list"],
            (underlying, expiry, option_type, True),
            (underlying, expiry, option_type),
            (underlying, expiry),
            (underlying,),
        )
        codes = option_codes(raw)[:limit]
        details = []
        for code in codes:
            try:
                details.append(option_detail_record(code, call_xtdata("get_option_detail_data", code)))
            except McpCoreError:
                details.append(option_detail_record(code, {"code": code}))
        return {
            "source": func,
            "underlying_code": underlying,
            "codes": codes,
            "details": details,
            "truncated": len(codes) >= limit,
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
        func, raw = _call_compatible(call_xtdata, ["get_option_undl_data"], (market,), ())
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
        details = [option_detail_record(code, call_xtdata("get_option_detail_data", code)) for code in clean_codes]
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
