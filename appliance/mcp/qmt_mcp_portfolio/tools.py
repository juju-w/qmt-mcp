"""MCP registration for read-only portfolio analysis."""

from __future__ import annotations

from typing import Any

from qmt_mcp_core.errors import McpCoreError, ok_envelope
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry
from qmt_mcp_xtdata.serializers import snapshot_records
from qmt_mcp_xttrade.serializers import asset_record, position_record, records

from .calculations import enrich_positions, exposure, portfolio_summary, risk_checks
from .thresholds import validate_thresholds

QUOTE_POLICIES = {"prefer_cache", "live", "cache_only"}


def _call_xtdata(func_name: str, *args: Any) -> Any:
    try:
        from xtquant import xtdata  # type: ignore
    except Exception as exc:
        raise McpCoreError("not_ready", "xtquant.xtdata is not importable from the broker pack") from exc
    func = getattr(xtdata, func_name, None)
    if func is None:
        raise McpCoreError("dependency", f"xtdata.{func_name} is unavailable in this xtquant version")
    try:
        return func(*args)
    except Exception as exc:
        raise McpCoreError("dependency", f"xtdata.{func_name} failed: {type(exc).__name__}: {exc}") from exc


def _validate_quote_policy(policy: str) -> str:
    if policy not in QUOTE_POLICIES:
        raise McpCoreError("validation", f"invalid quote_policy: {policy}", {"allowed": sorted(QUOTE_POLICIES)})
    return policy


def _quote_map(codes: list[str], quote_policy: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    policy = _validate_quote_policy(quote_policy)
    if not codes:
        return {}, {"quote_policy": policy, "source": "none"}
    if policy == "cache_only":
        raise McpCoreError("not_ready", "portfolio cache_only quote policy requires 013 cache bridge")
    raw = _call_xtdata("get_full_tick", codes)
    records_out = snapshot_records(raw, codes)
    return {record["code"]: record for record in records_out if record.get("last_price") is not None}, {
        "quote_policy": policy,
        "source": "get_full_tick",
        "requested": len(codes),
    }


def register_portfolio_tools(mcp: Any, registry: ToolRegistry, health: HealthState, session: Any) -> None:
    def load_portfolio(account_id: str, quote_policy: str = "prefer_cache") -> dict[str, Any]:
        aid = session.allowlist.require(account_id)
        asset_raw = session.query("query_stock_asset", aid)
        positions_raw = session.query("query_stock_positions", aid)
        asset = asset_record(asset_raw) if asset_raw is not None else {}
        positions = records(positions_raw, position_record)
        codes = [str(pos.get("code")) for pos in positions if pos.get("code")]
        quotes, quote_meta = _quote_map(codes, quote_policy)
        enriched, valuation = enrich_positions(asset, positions, quotes)
        summary = portfolio_summary(asset, enriched, valuation)
        metadata = {"account_id": aid, **quote_meta}
        if summary["diagnostics"]["missing_quotes"]:
            health.set_family(
                "portfolio", "degraded", "portfolio analysis has missing quotes", registry.tool_names("portfolio")
            )
        return {"account_id": aid, "asset": asset, "positions": enriched, "summary": summary, "metadata": metadata}

    @registry.register(
        mcp,
        name="qmt_portfolio_summary",
        family="portfolio",
        description="Read-only portfolio summary: assets, market value, cash ratio, concentration, quote coverage.",
        audit_fields=["account_id", "quote_policy"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_portfolio_summary(account_id: str, quote_policy: str = "prefer_cache") -> dict[str, Any]:
        data = load_portfolio(account_id, quote_policy)
        return ok_envelope(account_id=data["account_id"], metadata=data["metadata"], summary=data["summary"])

    @registry.register(
        mcp,
        name="qmt_portfolio_positions",
        family="portfolio",
        description="Read-only enriched portfolio positions with valuation, weights, P&L, and quote metadata.",
        audit_fields=["account_id", "quote_policy"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_portfolio_positions(account_id: str, quote_policy: str = "prefer_cache") -> dict[str, Any]:
        data = load_portfolio(account_id, quote_policy)
        return ok_envelope(account_id=data["account_id"], metadata=data["metadata"], positions=data["positions"])

    @registry.register(
        mcp,
        name="qmt_portfolio_exposure",
        family="portfolio",
        description="Read-only portfolio exposure grouped by market and instrument type.",
        audit_fields=["account_id", "quote_policy"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_portfolio_exposure(account_id: str, quote_policy: str = "prefer_cache") -> dict[str, Any]:
        data = load_portfolio(account_id, quote_policy)
        positions = data["positions"]
        return ok_envelope(
            account_id=data["account_id"],
            metadata=data["metadata"],
            exposure={
                "market": exposure(positions, "market"),
                "instrument_type": exposure(positions, "instrument_type"),
            },
        )

    @registry.register(
        mcp,
        name="qmt_portfolio_risk_checks",
        family="portfolio",
        description="Read-only threshold checks for concentration, cash ratio, and quote coverage.",
        audit_fields=["account_id", "quote_policy"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_portfolio_risk_checks(
        account_id: str,
        quote_policy: str = "prefer_cache",
        thresholds: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        clean_thresholds = validate_thresholds(thresholds)
        data = load_portfolio(account_id, quote_policy)
        checks = risk_checks(data["summary"], clean_thresholds)
        return ok_envelope(
            account_id=data["account_id"],
            metadata=data["metadata"],
            thresholds=clean_thresholds,
            checks=checks,
        )
