"""Input validation for xtdata MCP tools."""

from __future__ import annotations

import re
from collections.abc import Iterable

from qmt_mcp_core.errors import McpCoreError

CODE_RE = re.compile(r"^[0-9A-Za-z]+\.(SH|SZ|BJ|IF|SF|DF|INE|GF|ZF|SHO|SZO)$")
MARKET_RE = re.compile(r"^(SH|SZ|BJ|IF|SF|DF|INE|GF|ZF|SHO|SZO)$")
DATE_RE = re.compile(r"^$|^[0-9]{8}([0-9]{6})?$")

PERIODS = {"tick", "1m", "5m", "15m", "30m", "1h", "1d", "1w", "1mon", "1q", "1hy", "1y"}
DIVIDEND_TYPES = {"none", "front", "back", "front_ratio", "back_ratio"}
DEFAULT_BAR_FIELDS = ["open", "high", "low", "close", "volume", "amount"]
MAX_CODES = 50
MAX_DOWNLOAD_CODES = 200
MAX_SECTOR_LIMIT = 10000
QUOTE_CACHE_POLICIES = {"prefer", "cache_only", "live"}
QUOTE_BACKENDS = {"auto", "official_subscription", "whole_quote", "polling_fallback"}


def validate_code(code: str) -> str:
    if not CODE_RE.match(code):
        raise McpCoreError("validation", f"invalid instrument code: {code}", {"expected": "code.market"})
    return code


def validate_codes(codes: Iterable[str], *, max_codes: int = MAX_CODES) -> list[str]:
    result = [validate_code(code) for code in codes]
    if not result:
        raise McpCoreError("validation", "codes must not be empty")
    if len(result) > max_codes:
        raise McpCoreError("validation", "too many codes", {"max_codes": max_codes})
    return result


def validate_market(market: str) -> str:
    if not MARKET_RE.match(market):
        raise McpCoreError("validation", f"invalid market: {market}", {"expected": "market code such as SH or SZ"})
    return market


def validate_period(period: str) -> str:
    if period not in PERIODS:
        raise McpCoreError("validation", f"invalid period: {period}", {"allowed": sorted(PERIODS)})
    return period


def validate_date(value: str, name: str) -> str:
    if not DATE_RE.match(value or ""):
        raise McpCoreError("validation", f"invalid {name}: {value}", {"expected": "YYYYMMDD or YYYYMMDDHHmmSS"})
    return value or ""


def validate_dividend(value: str) -> str:
    if value not in DIVIDEND_TYPES:
        raise McpCoreError("validation", f"invalid dividend_type: {value}", {"allowed": sorted(DIVIDEND_TYPES)})
    return value


def validate_fields(fields: list[str] | None) -> list[str]:
    if not fields:
        return list(DEFAULT_BAR_FIELDS)
    clean = []
    for field in fields:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", field):
            raise McpCoreError("validation", f"invalid field name: {field}")
        clean.append(field)
    return clean


def validate_quote_cache_policy(policy: str) -> str:
    if policy not in QUOTE_CACHE_POLICIES:
        raise McpCoreError("validation", f"invalid cache_policy: {policy}", {"allowed": sorted(QUOTE_CACHE_POLICIES)})
    return policy


def validate_quote_backend(value: str) -> str:
    if value not in QUOTE_BACKENDS:
        raise McpCoreError("validation", f"invalid backend_preference: {value}", {"allowed": sorted(QUOTE_BACKENDS)})
    return value


def validate_positive_int(value: int, name: str, *, min_value: int, max_value: int) -> int:
    if value < min_value or value > max_value:
        raise McpCoreError("validation", f"{name} out of bounds", {"min": min_value, "max": max_value})
    return value
