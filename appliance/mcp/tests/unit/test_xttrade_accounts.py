"""Unit tests for xttrade account types / id validation / allowlist (feature 004)."""

from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_xttrade.accounts import AccountType, Allowlist, validate_account_id


def test_account_type_parse():
    assert AccountType.parse("stock") is AccountType.STOCK
    assert AccountType.parse("CREDIT") is AccountType.CREDIT
    with pytest.raises(McpCoreError) as exc:
        AccountType.parse("margin")
    assert exc.value.error_type == "config"


@pytest.mark.parametrize("good", ["1234567890", "8888", "A12345", "12345-01"])
def test_validate_account_id_ok(good):
    assert validate_account_id(good) == good


@pytest.mark.parametrize("bad", ["", "  ", "x", "has space", "a/b", "*" * 4])
def test_validate_account_id_bad(bad):
    with pytest.raises(McpCoreError) as exc:
        validate_account_id(bad)
    assert exc.value.error_type == "validation"


def test_allowlist_from_config_and_membership():
    al = Allowlist.from_config(" 111111, 222222 ,", "STOCK")
    assert al  # truthy
    assert al.ids() == ["111111", "222222"]
    assert al.account_type is AccountType.STOCK
    assert al.require("111111") == "111111"


def test_allowlist_refuses_unknown_account():
    al = Allowlist.from_config("111111", "STOCK")
    with pytest.raises(McpCoreError) as exc:
        al.require("999999")  # agent cannot widen the set via args
    assert exc.value.error_type == "validation"
    assert exc.value.details["account_id"] == "999999"


def test_empty_allowlist_is_falsey():
    assert not Allowlist.from_config("", "STOCK")
    assert not Allowlist.from_config("   ", "STOCK")
