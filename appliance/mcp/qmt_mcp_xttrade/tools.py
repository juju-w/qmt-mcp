"""Read-only xttrade account-query tools (feature 004).

Registered ONLY when enabled via flag + allowlist. Every tool: resolves the
account against the server allowlist (agent cannot widen it), is readiness-gated
(returns trader-not-ready when the session is down), worker-backed, audited, and
returns structured JSON. NO order/cancel/transfer/borrow/export tools exist here.
"""

from __future__ import annotations

from typing import Any

from qmt_mcp_core.errors import ok_envelope
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.registry import ToolRegistry

from .accounts import Allowlist
from .serializers import asset_record, generic_record, order_record, position_record, records, trade_record
from .session import TraderSession

ACCOUNT_ARG = "account id; MUST be on the server allowlist (the agent cannot add accounts)"


def register_xttrade_tools(
    mcp: Any,
    registry: ToolRegistry,
    health: HealthState,
    session: TraderSession,
    allowlist: Allowlist,
) -> None:
    @registry.register(
        mcp,
        name="qmt_xttrade_asset",
        family="xttrade_query",
        description=(
            "Read-only: return the cash/total/market-value/frozen asset snapshot for one allow-listed account. "
            f"`account_id`: {ACCOUNT_ARG}. Refuses trader-not-ready if QMT/xttrader is not connected."
        ),
        audit_fields=["account_id"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xttrade_asset(account_id: str) -> dict[str, Any]:
        aid = allowlist.require(account_id)
        raw = session.query("query_stock_asset", aid)
        return ok_envelope(account_id=aid, asset=asset_record(raw) if raw is not None else None)

    @registry.register(
        mcp,
        name="qmt_xttrade_positions",
        family="xttrade_query",
        description=(
            "Read-only: list holdings (code, volume, can-use/frozen/yesterday/on-road volume, open/avg price, "
            f"market value) for one allow-listed account. `account_id`: {ACCOUNT_ARG}."
        ),
        audit_fields=["account_id"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xttrade_positions(account_id: str) -> dict[str, Any]:
        aid = allowlist.require(account_id)
        raw = session.query("query_stock_positions", aid)
        return ok_envelope(account_id=aid, positions=records(raw, position_record))

    @registry.register(
        mcp,
        name="qmt_xttrade_orders",
        family="xttrade_query",
        description=(
            "Read-only: list today's orders for one allow-listed account. Set `cancelable_only=true` to return only "
            f"still-cancelable orders. `account_id`: {ACCOUNT_ARG}. This does NOT place or cancel anything."
        ),
        audit_fields=["account_id", "cancelable_only"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xttrade_orders(account_id: str, cancelable_only: bool = False) -> dict[str, Any]:
        aid = allowlist.require(account_id)
        raw = session.query("query_stock_orders", aid, bool(cancelable_only))
        return ok_envelope(account_id=aid, cancelable_only=bool(cancelable_only), orders=records(raw, order_record))

    @registry.register(
        mcp,
        name="qmt_xttrade_trades",
        family="xttrade_query",
        description=(
            "Read-only: list today's fills/trades (code, traded price/volume/amount, time, order id) for one "
            f"allow-listed account. `account_id`: {ACCOUNT_ARG}."
        ),
        audit_fields=["account_id"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xttrade_trades(account_id: str) -> dict[str, Any]:
        aid = allowlist.require(account_id)
        raw = session.query("query_stock_trades", aid)
        return ok_envelope(account_id=aid, trades=records(raw, trade_record))

    @registry.register(
        mcp,
        name="qmt_xttrade_position_statistics",
        family="xttrade_query",
        description=(
            "Read-only: aggregate position statistics for one allow-listed account (when the SDK provides it). "
            f"`account_id`: {ACCOUNT_ARG}."
        ),
        audit_fields=["account_id"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xttrade_position_statistics(account_id: str) -> dict[str, Any]:
        aid = allowlist.require(account_id)
        raw = session.query("query_position_statistics", aid)
        return ok_envelope(account_id=aid, statistics=records(raw, generic_record))

    @registry.register(
        mcp,
        name="qmt_xttrade_account_status",
        family="xttrade_query",
        description=(
            f"Read-only: report the trading account status for one allow-listed account. `account_id`: {ACCOUNT_ARG}."
        ),
        audit_fields=["account_id"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xttrade_account_status(account_id: str) -> dict[str, Any]:
        aid = allowlist.require(account_id)
        raw = session.query("query_account_status", aid)
        return ok_envelope(account_id=aid, status=generic_record(raw) if raw is not None else None)

    @registry.register(
        mcp,
        name="qmt_xttrade_new_purchase_limit",
        family="xttrade_query",
        description=(
            f"Read-only: new-share (IPO) purchase limit for one allow-listed account. `account_id`: {ACCOUNT_ARG}."
        ),
        audit_fields=["account_id"],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xttrade_new_purchase_limit(account_id: str) -> dict[str, Any]:
        aid = allowlist.require(account_id)
        raw = session.query("query_new_purchase_limit", aid)
        return ok_envelope(account_id=aid, limits=records(raw, generic_record))

    @registry.register(
        mcp,
        name="qmt_xttrade_ipo_data",
        family="xttrade_query",
        description="Read-only: today's IPO/new-issue data known to xttrader (not account-scoped). No arguments.",
        audit_fields=[],
        worker_backed=True,
        timeout=15,
    )
    def qmt_xttrade_ipo_data() -> dict[str, Any]:
        raw = session.query("query_ipo_data", account_scoped=False)
        return ok_envelope(ipo=records(raw, generic_record))
