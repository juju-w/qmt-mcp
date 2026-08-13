"""Interactive single-instrument K-line MCP App."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

from mcp.server.apps import Apps

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_xtdata.tools import instrument_display_name, read_bars_data
from qmt_mcp_xtdata.validation import validate_code

from .kline_data import build_kline_payload, kline_text

KLINE_RESOURCE_URI = "ui://qmt-mcp/kline-chart-v1.html"
KLINE_RESOURCE_NAME = "kline-chart-v1.html"
KLINE_TOOL_NAME = "qmt_xtdata_kline_chart"
KLINE_FIELDS = ["open", "high", "low", "close", "volume", "amount"]
KLINE_MAX_BARS = 1000

KLINE_DESCRIPTION = (
    "Render an interactive single-instrument K-line/candlestick chart with volume and MA5/MA10/MA20. Use this when "
    "the user asks to view, inspect, hover, zoom, or visually review ONE stock/ETF/index's price history. `code` must "
    "be one exact QMT code such as 688234.SH; if the user supplied a name, pinyin initials, theme, or ambiguous phrase, "
    "call qmt_xtdata_resolve_instrument first and do not guess. Args: `period` defaults to 1d and commonly supports "
    "1d/1w/1mon; optional `start_time`/`end_time` use YYYYMMDD[HHmmSS]; `count` defaults to 120 and is capped at "
    "1000; `dividend_type` supports none/front/back/front_ratio/back_ratio. Prefer qmt_xtdata_bars instead for raw "
    "numeric analysis, multiple codes, arbitrary fields, or more than 1000 rows. Returns concise text for non-App "
    "hosts plus chart-ready structured data; never downloads missing history or places trades."
)


def register_kline_app(registry: ToolRegistry, health: HealthState, warehouse=None) -> Apps:
    """Build the Apps extension before MCPServer consumes its contributions."""

    html = files("qmt_mcp_apps.resources").joinpath(KLINE_RESOURCE_NAME).read_text(encoding="utf-8")
    apps = Apps()
    apps.add_html_resource(
        KLINE_RESOURCE_URI,
        html,
        name="QMT K-Line Chart",
        title="QMT Interactive K-Line",
        description="Responsive candlestick, moving-average, and volume chart for one QMT instrument.",
        prefers_border=False,
    )

    @registry.register(
        apps,
        name=KLINE_TOOL_NAME,
        family="xtdata",
        title="QMT Interactive K-Line",
        description=KLINE_DESCRIPTION,
        audit_fields=["code", "period", "start_time", "end_time", "count", "dividend_type"],
        worker_backed=True,
        timeout=30,
        app_resource_uri=KLINE_RESOURCE_URI,
        text_renderer=kline_text,
    )
    def qmt_xtdata_kline_chart(
        code: str,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        count: int = 120,
        dividend_type: str = "front",
    ) -> dict[str, Any]:
        clean_code = validate_code(code)
        if count < 1 or count > KLINE_MAX_BARS:
            raise McpCoreError("validation", "count out of bounds", {"min": 1, "max": KLINE_MAX_BARS})
        result = read_bars_data(
            health,
            warehouse,
            codes=[clean_code],
            period=period,
            fields=KLINE_FIELDS,
            start_time=start_time,
            end_time=end_time,
            count=count,
            dividend_type=dividend_type,
        )
        return build_kline_payload(
            code=clean_code,
            name=instrument_display_name(clean_code),
            period=str(result["period"]),
            dividend_type=dividend_type,
            source=str(result["source"]),
            rows=list(result.get("rows") or []),
        )

    return apps
