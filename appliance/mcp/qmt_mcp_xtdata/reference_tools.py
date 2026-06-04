"""Optional read-only xtdata reference-data tools for 016."""

from __future__ import annotations

from typing import Any

from qmt_mcp_core.errors import McpCoreError, ok_envelope
from qmt_mcp_core.registry import ToolRegistry

from .reference_serializers import download_status, financial_groups, rows_from_any
from .validation import validate_code, validate_codes, validate_date

FINANCIAL_TABLES = {
    "Balance",
    "Income",
    "CashFlow",
    "Capital",
    "Holdernum",
    "Top10holder",
    "Top10flowholder",
    "Pershareindex",
}
REPORT_TYPES = {"report_time", "announce_time"}


def _validate_tables(tables: list[str] | None) -> list[str]:
    values = tables or ["Balance", "Income", "CashFlow"]
    bad = [table for table in values if table not in FINANCIAL_TABLES]
    if bad:
        raise McpCoreError(
            "validation", "invalid financial table", {"invalid": bad, "allowed": sorted(FINANCIAL_TABLES)}
        )
    return values


def _validate_report_type(value: str) -> str:
    if value not in REPORT_TYPES:
        raise McpCoreError("validation", f"invalid report_type: {value}", {"allowed": sorted(REPORT_TYPES)})
    return value


def register_reference_tools(mcp: Any, registry: ToolRegistry, call_xtdata) -> None:
    @registry.register(
        mcp,
        name="qmt_xtdata_financial_data",
        family="xtdata",
        description="Read optional xtdata financial statement tables for bounded codes/tables/date range.",
        audit_fields=["codes", "tables", "start_time", "end_time", "report_type"],
        worker_backed=True,
        timeout=60,
    )
    def qmt_xtdata_financial_data(
        codes: list[str],
        tables: list[str] | None = None,
        start_time: str = "",
        end_time: str = "",
        report_type: str = "report_time",
        limit: int = 5000,
    ) -> dict[str, Any]:
        clean_codes = validate_codes(codes, max_codes=200)
        clean_tables = _validate_tables(tables)
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        report = _validate_report_type(report_type)
        raw = call_xtdata("get_financial_data", clean_codes, clean_tables, start, end, report)
        groups, truncated = financial_groups(raw, limit=limit)
        return ok_envelope(source="get_financial_data", data=groups, truncated=truncated)

    @registry.register(
        mcp,
        name="qmt_xtdata_download_financial_data",
        family="xtdata",
        description="Download/cache optional financial data for one code/table/date range. Returns status only.",
        audit_fields=["code", "tables", "start_time", "end_time"],
        worker_backed=True,
        timeout=180,
    )
    def qmt_xtdata_download_financial_data(
        code: str, tables: list[str] | None = None, start_time: str = "", end_time: str = ""
    ) -> dict[str, Any]:
        clean_code = validate_code(code)
        clean_tables = _validate_tables(tables)
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        raw = call_xtdata("download_financial_data", clean_code, clean_tables, start, end)
        return ok_envelope(code=clean_code, tables=clean_tables, **download_status(raw))

    @registry.register(
        mcp,
        name="qmt_xtdata_dividend_factors",
        family="xtdata",
        description="Read optional xtdata dividend factors for one instrument.",
        audit_fields=["code"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_dividend_factors(code: str, limit: int = 5000) -> dict[str, Any]:
        clean_code = validate_code(code)
        rows, truncated = rows_from_any(call_xtdata("get_divid_factors", clean_code), limit=limit)
        return ok_envelope(code=clean_code, rows=rows, truncated=truncated)

    @registry.register(
        mcp,
        name="qmt_xtdata_ipo_info",
        family="xtdata",
        description="Read optional xtdata IPO/new-share reference data over a bounded date range.",
        audit_fields=["start_time", "end_time"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_ipo_info(start_time: str = "", end_time: str = "", limit: int = 5000) -> dict[str, Any]:
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        rows, truncated = rows_from_any(call_xtdata("get_ipo_info", start, end), limit=limit)
        return ok_envelope(start_time=start, end_time=end, rows=rows, truncated=truncated)

    @registry.register(
        mcp,
        name="qmt_xtdata_download_cb_data",
        family="xtdata",
        description="Download optional convertible-bond reference data. Returns status only.",
        audit_fields=[],
        worker_backed=True,
        timeout=120,
    )
    def qmt_xtdata_download_cb_data() -> dict[str, Any]:
        return ok_envelope(**download_status(call_xtdata("download_cb_data")))

    @registry.register(
        mcp,
        name="qmt_xtdata_cb_info",
        family="xtdata",
        description="Read optional convertible-bond reference data.",
        audit_fields=["code"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_cb_info(code: str = "", limit: int = 5000) -> dict[str, Any]:
        args = (validate_code(code),) if code else ()
        rows, truncated = rows_from_any(call_xtdata("get_cb_info", *args), limit=limit)
        return ok_envelope(code=code, rows=rows, truncated=truncated)

    @registry.register(
        mcp,
        name="qmt_xtdata_download_etf_info",
        family="xtdata",
        description="Download optional ETF creation/redemption reference data. Returns status only.",
        audit_fields=[],
        worker_backed=True,
        timeout=120,
    )
    def qmt_xtdata_download_etf_info() -> dict[str, Any]:
        return ok_envelope(**download_status(call_xtdata("download_etf_info")))

    @registry.register(
        mcp,
        name="qmt_xtdata_etf_info",
        family="xtdata",
        description="Read optional ETF creation/redemption reference data.",
        audit_fields=["code"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_etf_info(code: str = "", limit: int = 5000) -> dict[str, Any]:
        args = (validate_code(code),) if code else ()
        rows, truncated = rows_from_any(call_xtdata("get_etf_info", *args), limit=limit)
        return ok_envelope(code=code, rows=rows, truncated=truncated)

    @registry.register(
        mcp,
        name="qmt_xtdata_period_list",
        family="xtdata",
        description="Return periods supported by the installed xtdata runtime when available.",
        audit_fields=[],
        worker_backed=True,
        timeout=10,
    )
    def qmt_xtdata_period_list() -> dict[str, Any]:
        rows, _ = rows_from_any(call_xtdata("get_period_list"), limit=1000)
        return ok_envelope(periods=rows)
