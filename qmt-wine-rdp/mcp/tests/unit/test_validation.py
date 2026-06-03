"""Unit tests for xtdata input validation."""

from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_xtdata import validation as v


def test_validate_code_accepts_known_markets():
    assert v.validate_code("600000.SH") == "600000.SH"
    assert v.validate_code("000001.SZ") == "000001.SZ"


@pytest.mark.parametrize("bad", ["600000", "600000.XX", "abc", "600000.sh"])
def test_validate_code_rejects_bad(bad):
    with pytest.raises(McpCoreError) as exc:
        v.validate_code(bad)
    assert exc.value.error_type == "validation"


def test_validate_codes_empty_and_limit():
    with pytest.raises(McpCoreError):
        v.validate_codes([])
    with pytest.raises(McpCoreError) as exc:
        v.validate_codes(["600000.SH"] * 3, max_codes=2)
    assert exc.value.details["max_codes"] == 2


def test_validate_period():
    assert v.validate_period("1d") == "1d"
    with pytest.raises(McpCoreError):
        v.validate_period("2d")


def test_validate_date_allows_empty_and_formats():
    assert v.validate_date("", "start") == ""
    assert v.validate_date("20250101", "start") == "20250101"
    assert v.validate_date("20250101093000", "start") == "20250101093000"
    with pytest.raises(McpCoreError):
        v.validate_date("2025-01-01", "start")


def test_validate_dividend():
    assert v.validate_dividend("front") == "front"
    with pytest.raises(McpCoreError):
        v.validate_dividend("sideways")


def test_validate_fields_defaults_and_rejects():
    assert v.validate_fields(None) == v.DEFAULT_BAR_FIELDS
    assert v.validate_fields(["close", "volume"]) == ["close", "volume"]
    with pytest.raises(McpCoreError):
        v.validate_fields(["bad-name"])
