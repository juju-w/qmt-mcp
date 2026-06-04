"""Safety policy for local QMT custom-sector writes."""

from __future__ import annotations

from qmt_mcp_core.errors import McpCoreError

BUILTIN_SECTORS = {"沪深A股", "沪深ETF", "上证A股", "深证A股", "创业板", "科创板"}


def parse_prefixes(raw: str) -> list[str]:
    prefixes = [part.strip() for part in (raw or "").split(",") if part.strip()]
    if not prefixes:
        raise McpCoreError("config", "sector write prefixes must not be empty")
    return prefixes


def require_managed_sector(sector: str, prefixes: list[str]) -> str:
    name = (sector or "").strip()
    if not name:
        raise McpCoreError("validation", "sector name must not be empty")
    if name in BUILTIN_SECTORS:
        raise McpCoreError("validation", "refusing to mutate built-in sector", {"sector": name})
    if not any(name.startswith(prefix) for prefix in prefixes):
        raise McpCoreError("validation", "sector is outside allowed prefixes", {"sector": name, "prefixes": prefixes})
    return name


def require_confirm(confirm: bool) -> None:
    if not confirm:
        raise McpCoreError("validation", "destructive sector operation requires confirm=true")
