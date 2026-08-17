"""Fail-closed asset profile classification."""

from __future__ import annotations

from typing import Any

FINANCIAL_SECTORS = {"银行": "bank", "证券": "broker", "保险": "insurer"}


def classify_stock_profiles(codes: list[str], sector_members: dict[str, list[str] | None]) -> dict[str, Any]:
    missing = [sector for sector in FINANCIAL_SECTORS if sector_members.get(sector) is None]
    sets = {
        sector: set(sector_members.get(sector) or [])
        for sector in FINANCIAL_SECTORS
        if sector_members.get(sector) is not None
    }
    profiles = {}
    for code in codes:
        assigned = None
        for sector, profile in FINANCIAL_SECTORS.items():
            if code in sets.get(sector, set()):
                assigned = profile
                break
        profiles[code] = assigned or ("non_financial" if not missing else "unknown")
    return {
        "profiles": profiles,
        "complete": not missing,
        "missing_sectors": missing,
        "provenance": [f"xtdata-sector:{sector}" for sector in FINANCIAL_SECTORS if sector in sets],
    }


def etf_profile_for(exposure_id: str, name: str = "") -> str:
    if exposure_id in {"csi_300", "csi_500", "csi_1000", "sse_50", "star_50", "chinext"}:
        return "broad_market_equity"
    if exposure_id in {"hang_seng_tech", "nasdaq_100", "sp_500"}:
        return "cross_border_equity"
    text = str(name or "")
    if "债" in text:
        return "bond"
    if "黄金" in text or "商品" in text:
        return "commodity"
    if "货币" in text:
        return "money_market"
    return "sector_theme_equity"
