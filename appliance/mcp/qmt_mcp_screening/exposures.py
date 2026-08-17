"""Strict, reviewed ETF exposure aliases and membership rules."""

from __future__ import annotations

import re
from typing import Any

from qmt_mcp_core.errors import McpCoreError

EXPOSURES = {
    "csi_300": {
        "labels": {"zh-CN": "沪深300", "en": "CSI 300"},
        "aliases": ("沪深300", "CSI300", "HS300"),
        "required_name_tokens": ("沪深300",),
    },
    "csi_500": {
        "labels": {"zh-CN": "中证500", "en": "CSI 500"},
        "aliases": ("中证500", "CSI500", "ZZ500"),
        "required_name_tokens": ("中证500",),
    },
    "csi_1000": {
        "labels": {"zh-CN": "中证1000", "en": "CSI 1000"},
        "aliases": ("中证1000", "CSI1000", "ZZ1000"),
        "required_name_tokens": ("中证1000",),
    },
    "sse_50": {
        "labels": {"zh-CN": "上证50", "en": "SSE 50"},
        "aliases": ("上证50", "SSE50", "SZ50"),
        "required_name_tokens": ("上证50",),
    },
    "star_50": {
        "labels": {"zh-CN": "科创50", "en": "STAR 50"},
        "aliases": ("科创50", "STAR50", "KC50"),
        "required_name_tokens": ("科创50",),
    },
    "chinext": {
        "labels": {"zh-CN": "创业板", "en": "ChiNext"},
        "aliases": ("创业板", "创业板指", "CHINEXT", "CYB"),
        "required_name_tokens": ("创业板",),
    },
    "hang_seng_tech": {
        "labels": {"zh-CN": "恒生科技", "en": "Hang Seng TECH"},
        "aliases": ("恒生科技", "HSTECH", "HSKJ"),
        "required_name_tokens": ("恒生科技",),
    },
    "nasdaq_100": {
        "labels": {"zh-CN": "纳斯达克100", "en": "Nasdaq-100"},
        "aliases": ("纳斯达克100", "纳指100", "NASDAQ100", "NDX"),
        "required_name_tokens": ("纳斯达克100", "纳指100"),
        "match_any": True,
    },
    "sp_500": {
        "labels": {"zh-CN": "标普500", "en": "S&P 500"},
        "aliases": ("标普500", "SP500", "S&P500"),
        "required_name_tokens": ("标普500",),
    },
}


def normalize_exposure_text(value: Any) -> str:
    return re.sub(r"[^0-9A-Z\u3400-\u9fff]+", "", str(value or "").upper())


_ALIAS_TO_ID = {
    normalize_exposure_text(alias): exposure_id
    for exposure_id, definition in EXPOSURES.items()
    for alias in (exposure_id, *definition["aliases"])
}


def canonical_exposure(value: str) -> str:
    normalized = normalize_exposure_text(value)
    exposure_id = _ALIAS_TO_ID.get(normalized)
    if exposure_id is None:
        raise McpCoreError(
            "validation",
            f"unknown ETF exposure: {value}",
            {"query": value, "known_exposure_groups": sorted(EXPOSURES)},
        )
    return exposure_id


def match_exposure(record: dict[str, Any], exposure_id: str) -> bool:
    definition = EXPOSURES.get(exposure_id)
    if definition is None:
        return False
    if str(record.get("instrument_type") or "").lower() != "etf":
        return False
    name = normalize_exposure_text(record.get("name"))
    tokens = [normalize_exposure_text(token) for token in definition["required_name_tokens"]]
    if definition.get("match_any"):
        return any(token and token in name for token in tokens)
    return all(token and token in name for token in tokens)


def exposure_groups(locale: str = "zh-CN") -> list[dict[str, Any]]:
    language = locale if locale in {"zh-CN", "en"} else "en"
    return [
        {
            "id": exposure_id,
            "label": definition["labels"][language],
            "aliases": list(definition["aliases"]),
        }
        for exposure_id, definition in sorted(EXPOSURES.items())
    ]
