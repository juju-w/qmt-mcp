"""Gated custom-sector mutation tools for 017."""

from __future__ import annotations

from typing import Any

from qmt_mcp_core.errors import ok_envelope
from qmt_mcp_core.registry import ToolRegistry

from .sector_policy import parse_prefixes, require_confirm, require_managed_sector
from .validation import validate_codes


def register_sector_write_tools(mcp: Any, registry: ToolRegistry, config: Any, call_xtdata) -> None:
    prefixes = parse_prefixes(config.xtdata_sector_write_prefixes)

    @registry.register(
        mcp,
        name="qmt_xtdata_sector_create_folder",
        family="xtdata",
        description="Create a managed custom sector folder. Disabled unless QMT_ENABLE_XTDATA_SECTOR_WRITE=1.",
        audit_fields=["folder"],
        worker_backed=True,
        timeout=20,
    )
    def qmt_xtdata_sector_create_folder(folder: str) -> dict[str, Any]:
        clean = require_managed_sector(folder, prefixes)
        raw = call_xtdata("create_sector_folder", clean)
        return ok_envelope(folder=clean, status="created", raw_result=raw)

    @registry.register(
        mcp,
        name="qmt_xtdata_sector_create",
        family="xtdata",
        description="Create a managed custom sector.",
        audit_fields=["sector"],
        worker_backed=True,
        timeout=20,
    )
    def qmt_xtdata_sector_create(sector: str) -> dict[str, Any]:
        clean = require_managed_sector(sector, prefixes)
        raw = call_xtdata("create_sector", clean)
        return ok_envelope(sector=clean, status="created", raw_result=raw)

    @registry.register(
        mcp,
        name="qmt_xtdata_sector_add_codes",
        family="xtdata",
        description="Add validated codes to a managed custom sector.",
        audit_fields=["sector", "codes"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_sector_add_codes(sector: str, codes: list[str]) -> dict[str, Any]:
        clean = require_managed_sector(sector, prefixes)
        clean_codes = validate_codes(codes, max_codes=1000)
        raw = call_xtdata("add_sector", clean, clean_codes)
        return ok_envelope(sector=clean, codes=clean_codes, status="updated", raw_result=raw)

    @registry.register(
        mcp,
        name="qmt_xtdata_sector_remove_codes",
        family="xtdata",
        description="Remove validated codes from a managed custom sector.",
        audit_fields=["sector", "codes"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_sector_remove_codes(sector: str, codes: list[str]) -> dict[str, Any]:
        clean = require_managed_sector(sector, prefixes)
        clean_codes = validate_codes(codes, max_codes=1000)
        raw = call_xtdata("remove_stock_from_sector", clean, clean_codes)
        return ok_envelope(sector=clean, codes=clean_codes, status="updated", raw_result=raw)

    @registry.register(
        mcp,
        name="qmt_xtdata_sector_delete",
        family="xtdata",
        description="Delete a managed custom sector. Requires confirm=true.",
        audit_fields=["sector", "confirm"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_sector_delete(sector: str, confirm: bool = False) -> dict[str, Any]:
        require_confirm(confirm)
        clean = require_managed_sector(sector, prefixes)
        raw = call_xtdata("remove_sector", clean)
        return ok_envelope(sector=clean, status="deleted", raw_result=raw)

    @registry.register(
        mcp,
        name="qmt_xtdata_sector_reset",
        family="xtdata",
        description="Replace a managed custom sector's codes. Requires confirm=true.",
        audit_fields=["sector", "codes", "confirm"],
        worker_backed=True,
        timeout=30,
    )
    def qmt_xtdata_sector_reset(sector: str, codes: list[str], confirm: bool = False) -> dict[str, Any]:
        require_confirm(confirm)
        clean = require_managed_sector(sector, prefixes)
        clean_codes = validate_codes(codes, max_codes=1000)
        raw = call_xtdata("reset_sector", clean, clean_codes)
        return ok_envelope(sector=clean, codes=clean_codes, status="updated", raw_result=raw)

    @registry.register(
        mcp,
        name="qmt_xtdata_managed_sector_list",
        family="xtdata",
        description="List sectors that match configured managed prefixes.",
        audit_fields=[],
        worker_backed=True,
        timeout=20,
    )
    def qmt_xtdata_managed_sector_list() -> dict[str, Any]:
        raw = call_xtdata("get_sector_list")
        sectors = [sector for sector in (raw or []) if any(str(sector).startswith(prefix) for prefix in prefixes)]
        return ok_envelope(prefixes=prefixes, sectors=sectors)
