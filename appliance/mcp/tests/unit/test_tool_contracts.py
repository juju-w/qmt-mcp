"""Dependency-light unit tests for MCP tool visibility policy."""

from __future__ import annotations

import pytest

from qmt_mcp_core.tool_contracts import (
    ToolVisibilityPolicy,
    default_tool_title,
    oauth_scopes_allow,
    required_oauth_scopes,
)


@pytest.mark.parametrize(
    ("profile", "family", "read_only", "expected"),
    [
        ("full", "xtdata", False, True),
        ("readonly", "xtdata", True, True),
        ("readonly", "xtdata", False, False),
        ("market", "xtdata", False, True),
        ("market", "xttrade_query", True, False),
        ("account", "xttrade_query", True, True),
        ("account", "portfolio", True, True),
        ("account", "xtdata", True, False),
        ("core", "xtdata", True, False),
    ],
)
def test_profile_matrix(profile, family, read_only, expected):
    policy = ToolVisibilityPolicy(profile)
    assert policy.visible(name="qmt_example", family=family, read_only=read_only) is expected


def test_core_tools_ignore_allow_and_deny_filters():
    policy = ToolVisibilityPolicy("custom", ("qmt_xtdata_*",), ("qmt_*",))
    assert policy.visible(name="qmt_health", family="core", read_only=True) is True


def test_allowlist_intersects_and_denylist_removes():
    policy = ToolVisibilityPolicy(
        "full",
        ("qmt_xtdata_option_*", "qmt_xtdata_snapshot"),
        ("*_quotes",),
    )
    assert policy.visible(name="qmt_xtdata_snapshot", family="xtdata", read_only=True) is True
    assert policy.visible(name="qmt_xtdata_option_chain", family="xtdata", read_only=True) is True
    assert policy.visible(name="qmt_xtdata_option_quotes", family="xtdata", read_only=True) is False
    assert policy.visible(name="qmt_xtdata_bars", family="xtdata", read_only=True) is False


def test_custom_profile_requires_allowlist():
    with pytest.raises(ValueError, match="requires a non-empty allowlist"):
        ToolVisibilityPolicy("custom")


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="invalid tool profile"):
        ToolVisibilityPolicy("everything")


def test_default_title_is_human_readable():
    assert default_tool_title("qmt_xtdata_option_chain") == "QMT xtdata Option Chain"


@pytest.mark.parametrize(
    ("family", "read_only", "expected"),
    [
        ("core", True, ("qmt:read",)),
        ("xtdata", True, ("qmt:read", "qmt:market")),
        ("xtdata", False, ("qmt:read", "qmt:market", "qmt:manage")),
        ("xttrade_query", True, ("qmt:read", "qmt:account")),
        ("portfolio", True, ("qmt:read", "qmt:account")),
    ],
)
def test_required_oauth_scope_matrix(family, read_only, expected):
    assert required_oauth_scopes(family=family, read_only=read_only) == expected


def test_oauth_scope_policy_requires_base_and_all_tool_scopes():
    required = ("qmt:read", "qmt:market", "qmt:manage")
    assert oauth_scopes_allow(required, {"qmt:market", "qmt:manage"}) is False
    assert oauth_scopes_allow(required, {"qmt:read", "qmt:market"}) is False
    assert oauth_scopes_allow(required, {"qmt:read", "qmt:market", "qmt:manage"}) is True
    assert oauth_scopes_allow(required, {"qmt:read", "qmt:admin"}) is True
