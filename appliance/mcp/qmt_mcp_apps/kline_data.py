"""Dependency-light normalization and fallback text for the K-line App."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from qmt_mcp_core.errors import ok_envelope


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _time_key(value: Any) -> str:
    raw = str(value or "").strip()
    digits = "".join(character for character in raw if character.isdigit())
    if len(digits) in {8, 12, 14} and 1900 <= int(digits[:4]) <= 2200:
        return digits
    if digits:
        try:
            numeric = int(digits)
            if 19000101 <= numeric <= 22000101:
                return str(numeric)
            divisor = 1000 if numeric > 10_000_000_000 else 1
            return datetime.fromtimestamp(numeric / divisor).strftime("%Y%m%d%H%M%S")
        except (OverflowError, OSError, ValueError):
            pass
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%Y%m%d%H%M%S")
    except ValueError:
        return ""


def normalize_kline_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep chart-safe OHLCVA rows, sorted and deduplicated by timestamp."""

    by_time: dict[str, dict[str, Any]] = {}
    for row in rows:
        time = _time_key(row.get("time"))
        open_price = _finite(row.get("open"))
        high = _finite(row.get("high"))
        low = _finite(row.get("low"))
        close = _finite(row.get("close"))
        if not time or None in {open_price, high, low, close}:
            continue
        if min(open_price, high, low, close) <= 0 or high < max(open_price, close) or low > min(open_price, close):
            continue
        volume = max(0.0, _finite(row.get("volume")) or 0.0)
        amount = max(0.0, _finite(row.get("amount")) or 0.0)
        by_time[time] = {
            "time": time,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": amount,
        }
    return [by_time[key] for key in sorted(by_time)]


def build_kline_payload(
    *,
    code: str,
    name: str,
    period: str,
    dividend_type: str,
    source: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    bars = normalize_kline_rows(rows)
    latest = bars[-1] if bars else None
    previous = bars[-2] if len(bars) > 1 else None
    latest_close = latest["close"] if latest else None
    previous_close = previous["close"] if previous else None
    change = latest_close - previous_close if latest_close is not None and previous_close is not None else None
    change_percent = change / previous_close * 100 if change is not None and previous_close else None
    return ok_envelope(
        schema_version="1",
        instrument={"code": code, "name": name},
        period=period,
        dividend_type=dividend_type,
        source=source,
        range={
            "start": bars[0]["time"] if bars else "",
            "end": bars[-1]["time"] if bars else "",
            "bar_count": len(bars),
        },
        summary={
            "latest_close": latest_close,
            "previous_close": previous_close,
            "change": change,
            "change_percent": change_percent,
            "high": max((bar["high"] for bar in bars), default=None),
            "low": min((bar["low"] for bar in bars), default=None),
        },
        bars=bars,
    )


def _number(value: Any, *, percent: bool = False) -> str:
    number = _finite(value)
    if number is None:
        return "--"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}{'%' if percent else ''}"


def kline_text(payload: dict[str, Any]) -> str:
    """A useful fallback for hosts that cannot render MCP Apps."""

    if payload.get("ok") is not True:
        return (
            f"K-line request failed ({payload.get('error_type', 'unknown')}): {payload.get('error', 'unknown error')}"
        )
    instrument = payload.get("instrument") or {}
    range_ = payload.get("range") or {}
    summary = payload.get("summary") or {}
    name = instrument.get("name") or instrument.get("code") or "instrument"
    code = instrument.get("code") or ""
    return (
        f"{name} ({code}) {payload.get('period', '')} K-line: {range_.get('start') or '--'} to "
        f"{range_.get('end') or '--'}, {range_.get('bar_count', 0)} bars; latest close "
        f"{_number(summary.get('latest_close'))}, change {_number(summary.get('change'))} "
        f"({_number(summary.get('change_percent'), percent=True)}), range high {_number(summary.get('high'))}, "
        f"low {_number(summary.get('low'))}. Source: {payload.get('source', 'QMT xtdata')}."
    )
