"""Serializers for xtdata option APIs."""

from __future__ import annotations

from typing import Any

from .serializers import json_clean


def _first(data: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in data and data[name] not in (None, ""):
            return data[name]
    return None


def _option_type(raw: Any) -> str:
    text = str(raw or "").upper()
    if text in {"C", "CALL", "认购", "购"}:
        return "CALL"
    if text in {"P", "PUT", "认沽", "沽"}:
        return "PUT"
    if "CALL" in text or "认购" in text:
        return "CALL"
    if "PUT" in text or "认沽" in text:
        return "PUT"
    return text or "UNKNOWN"


def option_detail_record(code: str, raw: Any) -> dict[str, Any]:
    data = json_clean(raw) or {}
    if not isinstance(data, dict):
        data = {"value": data}
    raw_code = _first(data, "code", "opt_code", "option_code", "instrument_id") or code
    return {
        "code": str(raw_code),
        "name": _first(data, "name", "opt_name", "instrument_name"),
        "underlying_code": _first(data, "underlying_code", "undl_code", "underlying", "target_code"),
        "option_type": _option_type(_first(data, "option_type", "opt_type", "call_or_put", "cp_flag")),
        "expiry_date": str(_first(data, "expiry_date", "expire_date", "exercise_date", "maturity_date") or ""),
        "exercise_price": _first(data, "exercise_price", "strike", "strike_price", "行权价"),
        "contract_unit": _first(data, "contract_unit", "unit", "volume_multiple"),
        "risk_free_rate": _first(data, "risk_free_rate", "rfr"),
        "historical_volatility": _first(data, "historical_volatility", "hist_volatility", "hv"),
        "is_trading": _first(data, "is_trading", "trading", "status"),
        "raw_fields": data,
    }


def option_codes(raw: Any) -> list[str]:
    data = json_clean(raw) or []
    if isinstance(data, dict):
        values = data.get("codes") or data.get("data") or data.values()
    else:
        values = data
    out: list[str] = []
    for item in values if isinstance(values, list) else list(values):
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            code = _first(item, "code", "opt_code", "option_code", "instrument_id")
            if code:
                out.append(str(code))
    return list(dict.fromkeys(out))


def quote_midpoint(quote: dict[str, Any]) -> float | None:
    bid = quote.get("bid_price")
    ask = quote.get("ask_price")
    bid0 = bid[0] if isinstance(bid, list) and bid else bid
    ask0 = ask[0] if isinstance(ask, list) and ask else ask
    try:
        if bid0 and ask0:
            return (float(bid0) + float(ask0)) / 2
    except (TypeError, ValueError):
        return None
    return None
