#!/usr/bin/env python
"""QMT MCP launcher (read-only).

Composes the vendored qmt-trade-mcp servers into a single Bearer-token-guarded
SSE endpoint:

  * xtdata  -> all market-data tools
  * xttrade -> ONLY the read-only query_* tools (orders/cancels/transfers/
               securities-borrowing/export and the connect/callback/subscribe
               plumbing are removed)

The trader handshake (start + connect) is driven here in a background thread so
agents never see it; once MiniQMT is logged in, the query tools light up.

Vendored from yywx55/qmt-trade-mcp (MIT). See vendor/LICENSE and NOTICE.
"""
from __future__ import annotations

import os
import sys
import time
import random
import threading


def log(*a):
    print("[qmt-mcp]", *a, file=sys.stderr, flush=True)


# --- make the vendored packages importable ---------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.environ.get("QMT_MCP_VENDOR") or os.path.join(HERE, "vendor")
sys.path.insert(0, VENDOR)

from xtdata_mcp.server import mcp as xtdata_mcp  # noqa: E402
import xttrade_mcp.server as xtt  # noqa: E402

xttrade_mcp = xtt.mcp

# --- trade module: read-only allowlist -------------------------------------
TRADE_QUERY_ALLOW = {
    "query_stock_asset", "query_stock_orders", "query_stock_trades",
    "query_stock_positions", "query_position_statistics", "query_credit_detail",
    "query_stk_compacts", "query_credit_subjects", "query_credit_slo_code",
    "query_credit_assure", "query_new_purchase_limit", "query_ipo_data",
    "query_account_infos", "query_account_status", "query_com_fund",
    "query_com_position", "query_data", "smt_query_quoter", "smt_query_compact",
}

# Everything else on the trade server is stripped: order placement, cancels,
# fund transfer, securities borrowing, CSV export, and the lifecycle/callback/
# subscription plumbing (we drive the handshake ourselves).
TRADE_REMOVE = {
    "init_trader", "start_trader", "connect_trader", "stop_trader",
    "set_relaxed_response_order_enabled", "register_trader_callback",
    "subscribe_account", "unsubscribe_account",
    "order_stock", "order_stock_async",
    "cancel_order_stock", "cancel_order_stock_async",
    "cancel_order_stock_sysid", "cancel_order_stock_sysid_async",
    "fund_transfer", "smt_negotiate_order_async", "export_data",
}


def filter_trade_tools():
    for name in sorted(TRADE_REMOVE):
        try:
            xttrade_mcp.remove_tool(name)
        except Exception as exc:  # tool absent or already removed
            log(f"remove_tool({name}) skipped: {type(exc).__name__}: {exc}")
    # Defensive guard: anything not explicitly allow-listed must be gone.
    try:
        import asyncio
        remaining = set(asyncio.run(xttrade_mcp._list_tools()))
        remaining = {t.name if hasattr(t, "name") else str(t) for t in remaining} \
            if not isinstance(remaining, dict) else set(remaining)
    except Exception:
        remaining = set()
    leaked = {n for n in remaining if n not in TRADE_QUERY_ALLOW}
    for name in leaked:
        try:
            xttrade_mcp.remove_tool(name)
            log(f"defensively removed non-allowlisted tool: {name}")
        except Exception:
            pass
    log(f"trade tools kept (read-only): {sorted(remaining & TRADE_QUERY_ALLOW) or '?'}")


def _ensure_xtquant_on_path():
    """Put the broker pack's xtquant (resolved by detect-broker) on sys.path."""
    xtq = os.environ.get("QMT_XTQUANT_DIR_WIN", "").strip()
    if xtq and xtq not in sys.path:
        sys.path.insert(0, xtq)
        log(f"xtquant dir on sys.path: {xtq}")


# --- background trader connector -------------------------------------------
def connector():
    path = os.environ.get("QMT_USERDATA_WIN", "").strip()
    if not path:
        log("connector: QMT_USERDATA_WIN unset (no broker resolved); trader disabled")
        return
    retry = int(os.environ.get("QMT_CONNECT_RETRY", "8"))
    log(f"connector: waiting for MiniQMT at {path!r} (retry {retry}s)")
    _ensure_xtquant_on_path()
    while True:
        try:
            from xtquant import xttrader
            sid = random.randint(100_000, 2_000_000_000)
            t = xttrader.XtQuantTrader(path, sid)
            t.start()
            rc = t.connect()
            if rc == 0:
                xtt._trader = t
                log(f"trader connected (session_id={sid}); query tools live")
                return
            log(f"connect rc={rc}; MiniQMT not ready, retrying")
            try:
                t.stop()
            except Exception:
                pass
        except Exception as exc:
            log(f"connector: {type(exc).__name__}: {exc}")
        time.sleep(retry)


# --- Bearer token ASGI guard -----------------------------------------------
class BearerAuth:
    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and self.token:
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode()
            if auth != f"Bearer {self.token}":
                await send({
                    "type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                })
                await send({"type": "http.response.body", "body": b"unauthorized"})
                return
        await self.app(scope, receive, send)


def main():
    filter_trade_tools()
    xtdata_mcp.mount(xttrade_mcp)  # merge filtered trade tools into the data server

    token = os.environ.get("QMT_MCP_TOKEN", "").strip()
    if not token:
        log("WARNING: QMT_MCP_TOKEN is empty -- Bearer auth DISABLED")

    app = xtdata_mcp.http_app(transport="sse")
    app = BearerAuth(app, token)

    threading.Thread(target=connector, name="qmt-connector", daemon=True).start()

    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8765"))
    log(f"serving SSE on http://{host}:{port}/sse  (auth={'ON' if token else 'OFF'})")

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
