"""xttrader session: connect handshake + read-only query dispatch (feature 004).

The ONLY module that touches `xttrader` (lazily). `connect()` is used as the 005
connector's connect_fn; `query()` dispatches read-only `query_*` methods against an
allowlisted account. Read-only: this module calls NO order/cancel/transfer methods.

UNVERIFIED against a live permissioned account — written to the documented xttrader
interface. See specs/004 VERIFICATION for the amd64 validation checklist.
"""

from __future__ import annotations

import random
from typing import Any

from qmt_mcp_core.errors import McpCoreError

from .accounts import Allowlist


class TraderSession:
    def __init__(self, userdata_path: str, allowlist: Allowlist, session_id: int | None = None):
        self.userdata_path = userdata_path
        self.allowlist = allowlist
        self.session_id = session_id or random.randint(100_000, 999_999)
        self._trader: Any = None
        self._accounts: dict[str, Any] = {}

    def _account_obj(self, account_id: str) -> Any:
        obj = self._accounts.get(account_id)
        if obj is None:
            from xtquant.xttype import StockAccount  # type: ignore

            obj = StockAccount(account_id, self.allowlist.account_type.value)
            self._accounts[account_id] = obj
        return obj

    def is_connected(self) -> bool:
        return self._trader is not None

    def connect(self) -> str:
        """Connector connect_fn: returns connected | not_authorized | error."""
        try:
            from xtquant.xttrader import XtQuantTrader  # type: ignore
        except Exception:
            return "error"
        try:
            trader = XtQuantTrader(self.userdata_path, self.session_id)
            trader.start()
            ret = trader.connect()  # 0 == ok; -1 == not authorized / failed
        except Exception:
            return "error"
        if ret != 0:
            return "not_authorized" if ret == -1 else "error"
        self._trader = trader
        for aid in self.allowlist.ids():
            try:
                trader.subscribe(self._account_obj(aid))
            except Exception:
                continue
        return "connected"

    def query(self, method: str, account_id: str | None = None, *args: Any, account_scoped: bool = True) -> Any:
        if self._trader is None:
            raise McpCoreError("not_ready", "trader-not-ready")
        fn = getattr(self._trader, method, None)
        if fn is None or not callable(fn):
            raise McpCoreError("dependency", f"xttrader has no query method: {method}")
        if account_scoped:
            return fn(self._account_obj(account_id), *args)
        return fn(*args)
