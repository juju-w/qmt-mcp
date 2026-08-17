"""Pure market, liquidity, risk, and stock-size factor calculations."""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any

from .catalog import factor_definition
from .models import FactorObservation, finite_number

_SHARE_ALIASES = {
    "float": ("float_shares", "FloatVolume", "float_volume", "circulating_shares"),
    "total": ("total_shares", "TotalVolume", "total_volume", "shares"),
}


def _number(record: dict[str, Any], *names: str) -> float | None:
    for name in names:
        if name in record:
            value = finite_number(record.get(name))
            if value is not None:
                return value
    return None


def _bars(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        close = _number(row, "close", "Close")
        if close is None or close <= 0:
            continue
        normalized.append({**row, "close": close})
    return sorted(normalized, key=lambda row: str(row.get("time") or row.get("date") or ""))


def _missing(
    code: str,
    factor_id: str,
    params: dict[str, Any],
    reason: str,
    *,
    details: dict[str, Any] | None = None,
) -> FactorObservation:
    definition = factor_definition(factor_id)
    return FactorObservation.missing(
        code=code,
        factor_id=factor_id,
        params=params,
        reason=reason,
        unit=definition.unit,
        source="xtdata.market",
        details=details,
    )


def _available(
    code: str,
    factor_id: str,
    params: dict[str, Any],
    value: Any,
    *,
    rows: list[dict[str, Any]],
    details: dict[str, Any] | None = None,
) -> FactorObservation:
    definition = factor_definition(factor_id)
    data_as_of = str(rows[-1].get("time") or rows[-1].get("date") or "") if rows else ""
    return FactorObservation.available(
        code=code,
        factor_id=factor_id,
        params=params,
        value=value,
        unit=definition.unit,
        data_as_of=data_as_of,
        source="xtdata.market",
        adjustment=definition.adjustment,
        details=details,
    )


def _window(params: dict[str, Any], default: int) -> int:
    value = params.get("window", default)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) and value > 0 else default


def _close_return(rows: list[dict[str, Any]], window: int) -> float | None:
    if len(rows) < window + 1:
        return None
    start = rows[-window - 1]["close"]
    return rows[-1]["close"] / start - 1 if start > 0 else None


def _daily_returns(rows: list[dict[str, Any]], window: int) -> list[float] | None:
    if len(rows) < window + 1:
        return None
    closes = [row["close"] for row in rows[-window - 1 :]]
    return [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]


def _shares(instrument: dict[str, Any], kind: str) -> float | None:
    return _number(instrument, *_SHARE_ALIASES[kind])


def calculate_market_factor(
    *,
    code: str,
    factor_id: str,
    params: dict[str, Any],
    bars: list[dict[str, Any]] | None,
    instrument: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    peer_returns: list[float] | None = None,
    as_of: str = "",
) -> FactorObservation:
    """Calculate one catalog market factor from normalized plain-Python inputs."""

    if any(isinstance(row, dict) and row.get("_source_error") for row in (bars or [])):
        return _missing(code, factor_id, params, "source_error")
    rows = _bars(bars)
    instrument = instrument or {}
    snapshot = snapshot or {}

    if factor_id == "is_trading":
        raw = instrument.get("is_trading", instrument.get("IsTrading"))
        if raw is None and rows:
            raw = not bool(rows[-1].get("suspendFlag", 0))
        if raw is None:
            return _missing(code, factor_id, params, "missing_source_field")
        return _available(code, factor_id, params, bool(raw), rows=rows)

    if factor_id == "listing_days":
        raw_date = str(
            instrument.get("open_date") or instrument.get("OpenDate") or instrument.get("listing_date") or ""
        ).replace("-", "")[:8]
        end_date = (as_of or (str(rows[-1].get("time") or "")[:8] if rows else ""))[:8]
        try:
            days = (datetime.strptime(end_date, "%Y%m%d") - datetime.strptime(raw_date, "%Y%m%d")).days
        except ValueError:
            return _missing(code, factor_id, params, "missing_source_field")
        return _available(code, factor_id, params, max(days, 0), rows=rows)

    if factor_id == "bid_ask_spread_bps":
        source_reason = snapshot.get("missing_reason")
        if source_reason:
            return _missing(code, factor_id, params, str(source_reason))
        bid = _number(snapshot, "bid1", "bidPrice1", "bid_price_1")
        ask = _number(snapshot, "ask1", "askPrice1", "ask_price_1")
        if not bid or not ask:
            return _missing(code, factor_id, params, "one_sided_quote")
        if ask <= bid:
            return _missing(code, factor_id, params, "invalid_source_value", details={"bid1": bid, "ask1": ask})
        middle = (bid + ask) / 2
        return _available(
            code,
            factor_id,
            params,
            (ask - bid) / middle * 10_000,
            rows=rows,
            details={"bid1": bid, "ask1": ask, "quote_time": snapshot.get("time")},
        )

    if factor_id == "trading_ratio":
        window = _window(params, 60)
        if not rows:
            return _missing(code, factor_id, params, "insufficient_history")
        observed = rows[-window:]
        valid = sum(not bool(row.get("suspendFlag", 0)) for row in observed)
        return _available(
            code, factor_id, params, valid / window, rows=rows, details={"valid": valid, "expected": window}
        )

    if factor_id == "avg_amount":
        window = _window(params, 20)
        if len(rows) < window:
            return _missing(code, factor_id, params, "insufficient_history")
        amounts = [_number(row, "amount", "Amount") for row in rows[-window:]]
        if any(value is None or value < 0 for value in amounts):
            return _missing(code, factor_id, params, "missing_source_field")
        return _available(code, factor_id, params, statistics.fmean(amounts), rows=rows)

    if factor_id == "amount_ratio":
        window = _window(params, 20)
        if len(rows) < window + 1:
            return _missing(code, factor_id, params, "insufficient_history")
        latest = _number(rows[-1], "amount", "Amount")
        preceding = [_number(row, "amount", "Amount") for row in rows[-window - 1 : -1]]
        if latest is None or any(value is None for value in preceding):
            return _missing(code, factor_id, params, "missing_source_field")
        mean = statistics.fmean(preceding)
        if mean <= 0:
            return _missing(code, factor_id, params, "non_comparable_denominator")
        return _available(code, factor_id, params, latest / mean, rows=rows)

    if factor_id == "return":
        window = _window(params, 20)
        result = _close_return(rows, window)
        if result is None:
            return _missing(code, factor_id, params, "insufficient_history")
        return _available(code, factor_id, params, result, rows=rows)

    if factor_id == "ma_gap":
        window = _window(params, 20)
        if len(rows) < window:
            return _missing(code, factor_id, params, "insufficient_history")
        mean = statistics.fmean(row["close"] for row in rows[-window:])
        if mean <= 0:
            return _missing(code, factor_id, params, "non_comparable_denominator")
        return _available(code, factor_id, params, rows[-1]["close"] / mean - 1, rows=rows)

    if factor_id == "ma_alignment":
        if len(rows) < 120:
            return _missing(code, factor_id, params, "insufficient_history")
        close = rows[-1]["close"]
        ma20 = statistics.fmean(row["close"] for row in rows[-20:])
        ma60 = statistics.fmean(row["close"] for row in rows[-60:])
        ma120 = statistics.fmean(row["close"] for row in rows[-120:])
        state = "bullish" if close > ma20 > ma60 > ma120 else "bearish" if close < ma20 < ma60 < ma120 else "mixed"
        return _available(
            code, factor_id, params, state, rows=rows, details={"ma20": ma20, "ma60": ma60, "ma120": ma120}
        )

    if factor_id == "annualized_volatility":
        window = _window(params, 20)
        returns = _daily_returns(rows, window)
        if returns is None or len(returns) < 2:
            return _missing(code, factor_id, params, "insufficient_history")
        return _available(code, factor_id, params, statistics.stdev(returns) * math.sqrt(252), rows=rows)

    if factor_id == "max_drawdown":
        window = _window(params, 60)
        if len(rows) < window:
            return _missing(code, factor_id, params, "insufficient_history")
        peak = rows[-window]["close"]
        worst = 0.0
        for row in rows[-window:]:
            peak = max(peak, row["close"])
            worst = min(worst, row["close"] / peak - 1)
        return _available(code, factor_id, params, worst, rows=rows)

    if factor_id in {"float_market_cap", "total_market_cap"}:
        if not rows:
            return _missing(code, factor_id, params, "insufficient_history")
        kind = "float" if factor_id == "float_market_cap" else "total"
        share_count = _shares(instrument, kind)
        if share_count is None or share_count <= 0:
            return _missing(code, factor_id, params, "missing_source_field")
        return _available(code, factor_id, params, rows[-1]["close"] * share_count, rows=rows)

    if factor_id == "turnover_rate":
        window = _window(params, 20)
        share_count = _shares(instrument, "float")
        if len(rows) < window:
            return _missing(code, factor_id, params, "insufficient_history")
        if share_count is None or share_count <= 0:
            return _missing(code, factor_id, params, "missing_source_field")
        volumes = [_number(row, "volume", "Volume") for row in rows[-window:]]
        if any(value is None or value < 0 for value in volumes):
            return _missing(code, factor_id, params, "missing_source_field")
        return _available(code, factor_id, params, statistics.fmean(volumes) / share_count, rows=rows)

    if factor_id == "amihud_illiquidity":
        window = _window(params, 20)
        returns = _daily_returns(rows, window)
        if returns is None:
            return _missing(code, factor_id, params, "insufficient_history")
        amounts = [_number(row, "amount", "Amount") for row in rows[-window:]]
        if any(value is None or value <= 0 for value in amounts):
            return _missing(code, factor_id, params, "non_comparable_denominator")
        scale = 100_000_000
        result = statistics.fmean(abs(day_return) / amount for day_return, amount in zip(returns, amounts, strict=True))
        return _available(code, factor_id, params, result * scale, rows=rows, details={"scale": scale})

    if factor_id == "sector_relative_strength":
        window = _window(params, 20)
        own_return = _close_return(rows, window)
        peers = [value for value in (peer_returns or []) if finite_number(value) is not None]
        if own_return is None:
            return _missing(code, factor_id, params, "insufficient_history")
        if not peers:
            return _missing(code, factor_id, params, "exposure_unresolved")
        return _available(code, factor_id, params, own_return - statistics.median(peers), rows=rows)

    return _missing(code, factor_id, params, "unavailable_capability")
