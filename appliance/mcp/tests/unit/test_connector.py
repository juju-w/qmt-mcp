"""Unit tests for the trader connector (feature 005)."""

from __future__ import annotations

from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.connector import TraderConnector
from qmt_mcp_core.health import HealthState


def _health() -> HealthState:
    cfg = CoreConfig(
        broker_id="acme",
        broker_name="ACME",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token="s3cret",
        host="0.0.0.0",
        port=8765,
        transport="streamable-http",
        audit_path="/tmp/a.jsonl",
        worker_limit=2,
        allow_unauth_loopback=False,
        enable_xtdata=True,
        test_mode=True,
    )
    return HealthState(cfg)


def test_trader_not_ready_until_logged_in():
    h = _health()
    c = TraderConnector(h, connect_fn=lambda: "connected", is_logged_in=lambda: False)
    assert c.attempt() == "trader-not-ready"


def test_connects_when_logged_in():
    h = _health()
    c = TraderConnector(h, connect_fn=lambda: "connected", is_logged_in=lambda: True)
    assert c.attempt() == "connected"
    assert h.xttrade == "connected"


def test_not_authorized_maps_through():
    h = _health()
    c = TraderConnector(h, connect_fn=lambda: "not_authorized", is_logged_in=lambda: True)
    assert c.attempt() == "not_authorized"
    assert h.xttrade == "not_authorized"


def test_connect_exception_becomes_error_and_counts_attempt():
    h = _health()

    def boom():
        raise RuntimeError("handshake failed")

    c = TraderConnector(h, connect_fn=boom, is_logged_in=lambda: True)
    assert c.attempt() == "error"
    assert c.attempts == 1
    assert "RuntimeError" in h.last_error


def test_idempotent_when_already_connected():
    calls = {"n": 0}

    def connect():
        calls["n"] += 1
        return "connected"

    h = _health()
    c = TraderConnector(h, connect_fn=connect, is_logged_in=lambda: True, is_connected=lambda: True)
    assert c.attempt() == "connected"  # first connect
    assert c.attempt() == "connected"  # idempotent no-op
    assert calls["n"] == 1


def test_reconnects_after_drop():
    h = _health()
    connected = {"v": True}
    c = TraderConnector(
        h,
        connect_fn=lambda: "connected",
        is_logged_in=lambda: True,
        is_connected=lambda: connected["v"],
    )
    assert c.attempt() == "connected"
    connected["v"] = False  # session dropped
    assert c.attempt() == "connected"  # re-handshake


def test_backoff_grows_and_caps():
    h = _health()
    c = TraderConnector(
        h,
        connect_fn=lambda: "error",
        is_logged_in=lambda: True,
        backoff_base=1.0,
        backoff_max=10.0,
    )
    c.attempts = 0
    assert c.backoff_s() == 1.0
    c.attempts = 3
    assert c.backoff_s() == 8.0
    c.attempts = 20
    assert c.backoff_s() == 10.0  # capped
