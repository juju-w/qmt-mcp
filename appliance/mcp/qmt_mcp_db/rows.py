"""bars-row <-> warehouse-record mappers (pure; feature 012).

The xtdata bars tool yields rows like {code, time, open, high, low, close, volume,
amount, ...}. The warehouse stores the standard OHLCV columns keyed by
(broker_id, code, period, dividend_type, dt). Mappers are pure and host-testable.
"""

from __future__ import annotations

from typing import Any

OHLCV = ("open", "high", "low", "close", "volume", "amount")


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_record(broker_id: str, code: str, period: str, dividend_type: str, row: dict[str, Any]) -> dict[str, Any]:
    rec = {
        "broker_id": broker_id,
        "code": str(row.get("code") or code),
        "period": period,
        "dividend_type": dividend_type,
        "dt": str(row.get("time") or ""),
    }
    for field in OHLCV:
        rec[field] = _num(row.get(field))
    return rec


def to_records(broker_id: str, code: str, period: str, dividend_type: str, rows: list[dict[str, Any]]) -> list[dict]:
    out = []
    for row in rows:
        rec = to_record(broker_id, code, period, dividend_type, row)
        if rec["dt"]:  # never warehouse a row without a timestamp key
            out.append(rec)
    return out


def from_record(rec: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"code": rec.get("code"), "time": rec.get("dt")}
    for field in OHLCV:
        out[field] = rec.get(field)
    return out
