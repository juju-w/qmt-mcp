"""Unit tests for health/capability documents."""

from __future__ import annotations

from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.health import HealthState


def make_config(**overrides) -> CoreConfig:
    base = dict(
        broker_id="acme",
        broker_name="ACME",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token="s3cret",
        host="0.0.0.0",
        port=8765,
        transport="streamable-http",
        audit_path="/tmp/audit.jsonl",
        worker_limit=4,
        allow_unauth_loopback=False,
        enable_xtdata=True,
        test_mode=False,
    )
    base.update(overrides)
    return CoreConfig(**base)


def test_to_dict_has_expected_keys():
    health = HealthState(make_config())
    doc = health.to_dict()
    for key in (
        "ok",
        "server",
        "transport",
        "broker_config",
        "xtquant_import",
        "xtdata",
        "xttrade",
        "audit",
        "tool_families",
    ):
        assert key in doc
    assert doc["transport"] == "streamable-http"


def test_default_families_present():
    health = HealthState(make_config())
    families = {f["family"]: f for f in health.to_dict()["tool_families"]}
    assert families["core"]["state"] == "enabled"
    assert families["xttrade_query"]["state"] == "not_authorized"
    assert families["xttrade_write"]["state"] == "disabled"


def test_broker_config_missing_when_unknown():
    health = HealthState(make_config(broker_id="unknown"))
    assert health.to_dict()["broker_config"] == "missing"


def test_ok_flips_false_on_audit_error():
    health = HealthState(make_config())
    assert health.to_dict()["ok"] is True
    health.audit = "error"
    assert health.to_dict()["ok"] is False


def test_set_and_update_family_tools():
    health = HealthState(make_config())
    health.set_family("xtdata", "ready", "live", ["qmt_snapshot"])
    health.update_family_tools("xtdata", ["qmt_snapshot", "qmt_bars"])
    families = {f["family"]: f for f in health.capabilities()["tool_families"]}
    assert families["xtdata"]["state"] == "ready"
    assert families["xtdata"]["tools"] == ["qmt_snapshot", "qmt_bars"]


def test_capabilities_shape():
    cap = HealthState(make_config()).capabilities()
    assert cap["ok"] is True
    assert "tool_families" in cap
    assert "transport" in cap


def test_readiness_object_in_health():
    health = HealthState(make_config())
    health.qmt_login = "logged_in"
    health.xtdata = "ready"
    doc = health.to_dict()
    assert doc["readiness"]["qmt_login"] == "logged_in"
    assert doc["readiness"]["xtdata_state"] == "ready"
    assert doc["readiness"]["trader_state"] == health.xttrade


def test_readiness_states_do_not_flip_ok():
    health = HealthState(make_config())
    health.xtdata = "awaiting_login"
    health.xttrade = "not_authorized"
    assert health.to_dict()["ok"] is True  # readiness is reported, not fatal


def test_livez_is_minimal_and_secret_free():
    assert HealthState(make_config()).livez() == {"ok": True, "server": "live"}


def test_livez_unhealthy_when_server_error():
    health = HealthState(make_config())
    health.server = "error"
    assert health.livez()["ok"] is False
