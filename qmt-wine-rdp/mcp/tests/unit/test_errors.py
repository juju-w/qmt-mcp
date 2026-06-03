"""Unit tests for the uniform error envelope helpers."""

from __future__ import annotations

from qmt_mcp_core.errors import (
    McpCoreError,
    error_envelope,
    from_exception,
    ok_envelope,
    stack_summary,
)


def test_error_envelope_shape():
    env = error_envelope("validation", "bad input", {"field": "code"})
    assert env == {
        "ok": False,
        "error_type": "validation",
        "error": "bad input",
        "details": {"field": "code"},
    }


def test_unknown_error_type_coerced_to_internal():
    env = error_envelope("nonsense", "boom")
    assert env["error_type"] == "internal"
    assert env["details"] == {}


def test_ok_envelope():
    assert ok_envelope(count=3) == {"ok": True, "count": 3}


def test_mcp_core_error_coerces_bad_type():
    err = McpCoreError("not-a-type", "msg")
    assert err.error_type == "internal"
    assert str(err) == "msg"


def test_from_exception_preserves_mcp_core_error():
    err = McpCoreError("not_authorized", "no permission", {"account": "x"})
    env = from_exception(err)
    assert env["error_type"] == "not_authorized"
    assert env["details"] == {"account": "x"}


def test_from_exception_generic_can_hide_message():
    env = from_exception(ValueError("secret detail"), expose_message=False)
    assert env["error_type"] == "internal"
    assert env["error"] == "internal error"


def test_stack_summary_is_string():
    out = stack_summary(ValueError("x"))
    assert "ValueError" in out
