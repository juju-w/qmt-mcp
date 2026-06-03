"""Unit tests for the readiness probe state machine (feature 005)."""

from __future__ import annotations

from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState
from qmt_mcp_core.readiness import ReadinessProbe


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


def _probe(health, fs, sdk):
    return ReadinessProbe(health, fs_ready=lambda: fs(), sdk_ready=lambda: sdk(), poll_s=0.1)


def test_awaiting_login_when_no_fs_signal():
    h = _health()
    p = _probe(h, lambda: False, lambda: True)
    assert p.step() == "awaiting_login"
    assert h.qmt_login == "awaiting"
    assert h.last_probe_at  # timestamp set


def test_ready_when_fs_and_sdk_ok():
    h = _health()
    p = _probe(h, lambda: True, lambda: True)
    assert p.step() == "ready"
    assert h.qmt_login == "logged_in"
    assert h.last_error == ""


def test_degraded_when_logged_in_but_sdk_fails():
    h = _health()
    p = _probe(h, lambda: True, lambda: False)
    assert p.step() == "degraded"
    assert h.qmt_login == "logged_in"


def test_sdk_exception_is_captured_not_raised():
    h = _health()

    def boom():
        raise RuntimeError("xtdata not loaded")

    p = _probe(h, lambda: True, boom)
    assert p.step() == "degraded"
    assert "RuntimeError" in h.last_error


def test_recovers_to_ready_after_sdk_returns():
    h = _health()
    flag = {"ok": False}
    p = _probe(h, lambda: True, lambda: flag["ok"])
    assert p.step() == "degraded"
    flag["ok"] = True
    assert p.step() == "ready"
    assert h.last_error == ""


def test_login_lost_returns_to_awaiting():
    h = _health()
    fs = {"up": True}
    p = _probe(h, lambda: fs["up"], lambda: True)
    assert p.step() == "ready"
    fs["up"] = False
    assert p.step() == "awaiting_login"
    assert h.qmt_login == "awaiting"
