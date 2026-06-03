"""JSON-clean serialization helpers for xtdata outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def json_clean(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return json_clean(value.item())
        except Exception:
            pass
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_clean(v) for v in value]
    if hasattr(value, "to_dict"):
        try:
            return json_clean(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return json_clean(value.tolist())
        except Exception:
            pass
    return str(value)


def snapshot_records(raw: Any, codes: list[str]) -> list[dict[str, Any]]:
    data = json_clean(raw) or {}
    records = []
    for code in codes:
        item = data.get(code, {}) if isinstance(data, dict) else {}
        if not isinstance(item, dict):
            item = {"value": item}
        records.append(
            {
                "code": code,
                "time": item.get("time") or item.get("stime") or item.get("datetime") or "",
                "last_price": item.get("lastPrice", item.get("last_price", item.get("price"))),
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "pre_close": item.get("preClose", item.get("pre_close", item.get("lastClose"))),
                "volume": item.get("volume"),
                "amount": item.get("amount"),
                "bid_price": item.get("bidPrice", item.get("bid_price", [])),
                "bid_volume": item.get("bidVol", item.get("bid_volume", [])),
                "ask_price": item.get("askPrice", item.get("ask_price", [])),
                "ask_volume": item.get("askVol", item.get("ask_volume", [])),
                "raw_fields": item,
            }
        )
    return records


def _is_field_name(value: str, fields: set[str]) -> bool:
    return value in fields or value.lower() in fields


def _set_row(
    rows_by_key: dict[tuple[str, str], dict[str, Any]], code: str, time_value: Any, field: str, value: Any
) -> None:
    key = (code, str(time_value))
    row = rows_by_key.setdefault(key, {"code": code, "time": str(time_value)})
    row[field] = value


def _append_code_outer(
    rows_by_key: dict[tuple[str, str], dict[str, Any]],
    code: str,
    payload: dict[str, Any],
    fields: set[str],
) -> None:
    field_keys = [key for key in payload if _is_field_name(str(key), fields)]
    if field_keys:
        # get_market_data_ex commonly becomes {code: {field: {time: value}}}.
        for field in field_keys:
            by_time = payload.get(field)
            if isinstance(by_time, dict):
                for ts, value in by_time.items():
                    _set_row(rows_by_key, code, ts, str(field), value)
            else:
                _set_row(rows_by_key, code, "", str(field), by_time)
        return

    # Some dataframe conversions produce {code: {time: {field: value}}}.
    for ts, by_field in payload.items():
        if isinstance(by_field, dict):
            for field, value in by_field.items():
                _set_row(rows_by_key, code, ts, str(field), value)
        else:
            _set_row(rows_by_key, code, ts, "value", by_field)


def _append_field_outer(
    rows_by_key: dict[tuple[str, str], dict[str, Any]],
    field: str,
    payload: dict[str, Any],
    codes: set[str],
) -> None:
    code_keys = [key for key in payload if str(key) in codes]
    if code_keys:
        # Shape: {field: {code: {time: value}}}
        for code in code_keys:
            by_time = payload.get(code)
            if isinstance(by_time, dict):
                for ts, value in by_time.items():
                    _set_row(rows_by_key, str(code), ts, field, value)
            else:
                _set_row(rows_by_key, str(code), "", field, by_time)
        return

    # get_market_data commonly becomes {field: {time: {code: value}}}.
    for ts, by_code in payload.items():
        if isinstance(by_code, dict):
            for code, value in by_code.items():
                if not codes or str(code) in codes:
                    _set_row(rows_by_key, str(code), ts, field, value)


def bars_rows(raw: Any, codes: list[str], fields: list[str]) -> list[dict[str, Any]]:
    clean = json_clean(raw)
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    if isinstance(clean, dict):
        code_set = set(codes)
        field_set = set(fields)
        outer_keys = {str(key) for key in clean}

        if outer_keys & code_set:
            for code in codes:
                payload = clean.get(code)
                if isinstance(payload, dict):
                    _append_code_outer(rows_by_key, code, payload, field_set)
        else:
            field_names = [field for field in fields if field in clean] or list(clean.keys())
            for field in field_names:
                payload = clean.get(field)
                if isinstance(payload, dict):
                    _append_field_outer(rows_by_key, str(field), payload, code_set)

        if rows_by_key:
            return sorted(rows_by_key.values(), key=lambda row: (row.get("code", ""), row.get("time", "")))
    return [{"code": code, "time": "", "raw_fields": clean} for code in codes]


def date_strings(raw: Any) -> list[str]:
    clean = json_clean(raw) or []
    values = clean if isinstance(clean, list) else [clean]
    result = []
    for value in values:
        if isinstance(value, str):
            digits = "".join(ch for ch in value if ch.isdigit())
            result.append(digits[:8] if len(digits) >= 8 else value)
            continue
        if isinstance(value, (int, float)):
            if 19000101 <= int(value) <= 22000101:
                result.append(str(int(value)))
                continue
            divisor = 1000 if value > 10_000_000_000 else 1
            result.append(datetime.fromtimestamp(value / divisor).strftime("%Y%m%d"))
    return result
