"""Shared fixtures for the QMT MCP test suite.

The unit tier needs no third-party runtime deps. Fixtures here keep the
environment isolated and provide a fake `xtquant` for the (optional) integration
tier so app assembly can be exercised without Wine or a real broker pack.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def tmp_audit_path(tmp_path: Path) -> str:
    """A writable audit file path inside a temp dir."""
    return str(tmp_path / "logs" / "audit.jsonl")


@pytest.fixture(autouse=True)
def _isolate_mcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip QMT_*/MCP_* env so config tests see declared defaults, not the host."""
    for key in list(os.environ):
        if key.startswith(("QMT_", "MCP_")):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def fake_xtquant(monkeypatch: pytest.MonkeyPatch):
    """Inject a minimal fake `xtquant.xtdata` so imports succeed off-Wine.

    Used by the integration tier. Returns the fake xtdata module so a test can
    assert against recorded calls.
    """
    xtquant = types.ModuleType("xtquant")
    xtdata = types.ModuleType("xtquant.xtdata")

    def _noop(*args, **kwargs):
        return {}

    for name in (
        "connect",
        "get_client",
        "subscribe_quote",
        "get_full_tick",
        "get_market_data",
        "get_market_data_ex",
        "get_trading_dates",
        "get_stock_list_in_sector",
    ):
        setattr(xtdata, name, _noop)

    xtquant.xtdata = xtdata  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xtquant", xtquant)
    monkeypatch.setitem(sys.modules, "xtquant.xtdata", xtdata)
    return xtdata
