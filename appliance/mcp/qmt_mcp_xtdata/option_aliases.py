"""Small option-family alias map for 015."""

from __future__ import annotations

OPTION_FAMILY_ALIASES = {
    "50": "510050.SH",
    "50ETF": "510050.SH",
    "上证50": "510050.SH",
    "上证50ETF": "510050.SH",
    "中证50": "510050.SH",
    "SSE50": "510050.SH",
    "SZ50": "510050.SH",
    "300": "510300.SH",
    "300ETF": "510300.SH",
    "沪深300": "510300.SH",
    "沪深300ETF": "510300.SH",
    "HS300": "510300.SH",
    "CSI300": "510300.SH",
    "500": "510500.SH",
    "500ETF": "510500.SH",
    "中证500": "510500.SH",
    "中证500ETF": "510500.SH",
    "CSI500": "510500.SH",
    "ZZ500": "510500.SH",
    "科创50": "588000.SH",
    "科创50ETF": "588000.SH",
    "创业板": "159915.SZ",
    "创业板ETF": "159915.SZ",
}


def resolve_option_underlying(value: str) -> str:
    return OPTION_FAMILY_ALIASES.get(value, value)
