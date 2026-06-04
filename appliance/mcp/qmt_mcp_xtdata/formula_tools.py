"""Gated formula/factor runtime tools for 018."""

from __future__ import annotations

from typing import Any

from qmt_mcp_core.errors import McpCoreError, ok_envelope
from qmt_mcp_core.registry import ToolRegistry

from .formula_cache import FormulaCache
from .formula_policy import FormulaPolicy
from .serializers import json_clean
from .validation import validate_code, validate_codes, validate_date, validate_dividend, validate_period


def register_formula_tools(mcp: Any, registry: ToolRegistry, config: Any, call_xtdata) -> None:
    policy = FormulaPolicy(config.formula_allowlist, config.formula_output_sandbox)
    if not policy.allowed:
        raise McpCoreError("config", "QMT_FORMULA_ALLOWLIST is required when formula runtime is enabled")
    cache = FormulaCache()
    subscriptions: dict[str, dict[str, Any]] = {}

    @registry.register(
        mcp,
        name="qmt_xtdata_formula_call",
        family="xtdata",
        description="Call one allowlisted xtdata formula over a bounded code/date/count request.",
        audit_fields=["formula_name", "code", "period", "start_time", "end_time"],
        worker_backed=True,
        timeout=60,
    )
    def qmt_xtdata_formula_call(
        formula_name: str,
        code: str,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        formula = policy.require_formula(formula_name)
        clean_code = validate_code(code)
        clean_period = validate_period(period)
        start = validate_date(start_time, "start_time")
        end = validate_date(end_time, "end_time")
        div = validate_dividend(dividend_type)
        if count < -1 or count > 10000:
            raise McpCoreError("validation", "count out of bounds", {"min": -1, "max": 10000})
        raw = call_xtdata("call_formula", formula, clean_code, clean_period, start, end, count, div, params or {})
        return ok_envelope(formula_name=formula, code=clean_code, result=json_clean(raw))

    @registry.register(
        mcp,
        name="qmt_xtdata_formula_call_batch",
        family="xtdata",
        description="Call one allowlisted formula for a bounded code list.",
        audit_fields=["formula_name", "codes", "period", "start_time", "end_time"],
        worker_backed=True,
        timeout=120,
    )
    def qmt_xtdata_formula_call_batch(
        formula_name: str,
        codes: list[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        formula = policy.require_formula(formula_name)
        clean_codes = validate_codes(codes, max_codes=200)
        raw = call_xtdata(
            "call_formula_batch",
            formula,
            clean_codes,
            validate_period(period),
            validate_date(start_time, "start_time"),
            validate_date(end_time, "end_time"),
            count,
            validate_dividend(dividend_type),
            params or {},
        )
        return ok_envelope(formula_name=formula, codes=clean_codes, result=json_clean(raw))

    @registry.register(
        mcp,
        name="qmt_xtdata_formula_generate_factor",
        family="xtdata",
        description="Run allowlisted generate_index_data into the configured sandbox path.",
        audit_fields=["formula_name", "result_path"],
        worker_backed=True,
        timeout=300,
    )
    def qmt_xtdata_formula_generate_factor(
        formula_name: str, result_path: str = "", params: dict[str, Any] | None = None
    ):
        formula = policy.require_formula(formula_name)
        clean_path = policy.require_output_path(result_path)
        raw = call_xtdata("generate_index_data", formula, clean_path, params or {})
        return ok_envelope(formula_name=formula, result_path=clean_path, status="generated", raw_result=json_clean(raw))

    @registry.register(
        mcp,
        name="qmt_xtdata_formula_subscribe",
        family="xtdata",
        description="Subscribe to an allowlisted formula and cache latest callback output.",
        audit_fields=["formula_name", "code", "period"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_formula_subscribe(formula_name: str, code: str, period: str = "tick") -> dict[str, Any]:
        formula = policy.require_formula(formula_name)
        clean_code = validate_code(code)
        clean_period = validate_period(period)

        def callback(payload):
            cache.put(f"{formula}:{clean_code}:{clean_period}", payload)

        sid = call_xtdata("subscribe_formula", formula, clean_code, clean_period, callback)
        subscriptions[str(sid)] = {
            "subscription_id": sid,
            "formula_name": formula,
            "code": clean_code,
            "period": clean_period,
        }
        return ok_envelope(subscription=subscriptions[str(sid)])

    @registry.register(
        mcp,
        name="qmt_xtdata_formula_unsubscribe",
        family="xtdata",
        description="Unsubscribe from a formula subscription id.",
        audit_fields=["subscription_id"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_formula_unsubscribe(subscription_id: str) -> dict[str, Any]:
        raw = call_xtdata("unsubscribe_formula", int(subscription_id))
        sub = subscriptions.pop(str(subscription_id), {"subscription_id": subscription_id})
        return ok_envelope(subscription=sub, status="unsubscribed", raw_result=json_clean(raw))

    @registry.register(
        mcp,
        name="qmt_xtdata_formula_subscriptions",
        family="xtdata",
        description="List formula subscriptions for this MCP process.",
        audit_fields=[],
        worker_backed=False,
    )
    def qmt_xtdata_formula_subscriptions() -> dict[str, Any]:
        return ok_envelope(subscriptions=list(subscriptions.values()))

    @registry.register(
        mcp,
        name="qmt_xtdata_formula_cache",
        family="xtdata",
        description="Return latest-only formula callback cache status.",
        audit_fields=[],
        worker_backed=False,
    )
    def qmt_xtdata_formula_cache() -> dict[str, Any]:
        return ok_envelope(**cache.status())
