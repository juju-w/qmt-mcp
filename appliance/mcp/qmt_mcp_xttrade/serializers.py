"""Structured serializers for xttrader objects (feature 004).

xttrader returns SDK objects with `m_*` attributes (e.g. XtAsset.m_dCash). We map
the well-known fields to clean names and ALSO attach a defensive `raw` dump of all
`m_*` attributes — so an output is structured (constitution IV) yet resilient to
minor attribute-name differences across xtquant versions. Pure + host-testable
with fake objects.
"""

from __future__ import annotations

from typing import Any

from qmt_mcp_xtdata.serializers import json_clean


def raw_m_fields(obj: Any) -> dict[str, Any]:
    """Collect all `m_*` attributes of an xtquant SDK object into a clean dict."""
    out: dict[str, Any] = {}
    for name in dir(obj):
        if name.startswith("m_"):
            try:
                out[name] = json_clean(getattr(obj, name))
            except Exception:
                continue
    return out


def _first(obj: Any, *names: str) -> Any:
    for name in names:
        if hasattr(obj, name):
            return json_clean(getattr(obj, name))
    return None


def asset_record(obj: Any) -> dict[str, Any]:
    return {
        "account_id": _first(obj, "m_strAccountID", "account_id"),
        "cash": _first(obj, "m_dCash", "cash"),
        "frozen_cash": _first(obj, "m_dFrozenCash", "frozen_cash"),
        "market_value": _first(obj, "m_dMarketValue", "market_value"),
        "total_asset": _first(obj, "m_dTotalAsset", "total_asset"),
        "raw": raw_m_fields(obj),
    }


def position_record(obj: Any) -> dict[str, Any]:
    return {
        "account_id": _first(obj, "m_strAccountID"),
        "code": _first(obj, "m_strInstrumentID", "m_strStockCode"),
        "volume": _first(obj, "m_nVolume"),
        "can_use_volume": _first(obj, "m_nCanUseVolume"),
        "frozen_volume": _first(obj, "m_nFrozenVolume"),
        "yesterday_volume": _first(obj, "m_nYesterdayVolume"),
        "on_road_volume": _first(obj, "m_nOnRoadVolume"),
        "open_price": _first(obj, "m_dOpenPrice"),
        "avg_price": _first(obj, "m_dAvgPrice"),
        "market_value": _first(obj, "m_dMarketValue"),
        "raw": raw_m_fields(obj),
    }


def order_record(obj: Any) -> dict[str, Any]:
    return {
        "account_id": _first(obj, "m_strAccountID"),
        "order_id": _first(obj, "m_nOrderID", "m_strOrderSysID"),
        "code": _first(obj, "m_strInstrumentID", "m_strStockCode"),
        "order_type": _first(obj, "m_nOrderType"),
        "price": _first(obj, "m_dPrice"),
        "order_volume": _first(obj, "m_nOrderVolume"),
        "traded_volume": _first(obj, "m_nTradedVolume"),
        "traded_price": _first(obj, "m_dTradedPrice"),
        "order_status": _first(obj, "m_nOrderStatus"),
        "status_msg": _first(obj, "m_strStatusMsg"),
        "order_time": _first(obj, "m_strOrderTime", "m_nOrderTime"),
        "remark": _first(obj, "m_strOrderRemark"),
        "raw": raw_m_fields(obj),
    }


def trade_record(obj: Any) -> dict[str, Any]:
    return {
        "account_id": _first(obj, "m_strAccountID"),
        "trade_id": _first(obj, "m_strTradeID"),
        "order_id": _first(obj, "m_nOrderID", "m_strOrderSysID"),
        "code": _first(obj, "m_strInstrumentID", "m_strStockCode"),
        "order_type": _first(obj, "m_nOrderType"),
        "traded_price": _first(obj, "m_dPrice", "m_dTradedPrice"),
        "traded_volume": _first(obj, "m_nVolume", "m_nTradedVolume"),
        "traded_amount": _first(obj, "m_dTradeAmount"),
        "traded_time": _first(obj, "m_strTradeTime", "m_nTradedTime"),
        "raw": raw_m_fields(obj),
    }


def generic_record(obj: Any) -> dict[str, Any]:
    """Fallback structured record for less-common query objects (status, etc.)."""
    return {"raw": raw_m_fields(obj)}


def records(raw: Any, mapper) -> list[dict[str, Any]]:
    """Map a list (or single) of SDK objects through `mapper`."""
    if raw is None:
        return []
    items = raw if isinstance(raw, (list, tuple)) else [raw]
    return [mapper(obj) for obj in items]
