"""Bounded xtdata source adapter for screening orchestration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from qmt_mcp_xtdata.reference_serializers import financial_groups
from qmt_mcp_xtdata.serializers import bars_rows, snapshot_records

from .catalog import FACTOR_VERSION
from .models import DataContext, finite_number

DAILY_FIELDS = ["open", "high", "low", "close", "volume", "amount", "suspendFlag"]
MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")
MAX_SOURCE_ERRORS = 100


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def _quote_epoch_ms(value: Any) -> int | None:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    if len(digits) >= 14 and digits[:2] in {"19", "20"}:
        try:
            parsed = datetime.strptime(digits[:14], "%Y%m%d%H%M%S").replace(tzinfo=MARKET_TIMEZONE)
        except ValueError:
            pass
        else:
            milliseconds = int(digits[14:17].ljust(3, "0")) if len(digits) >= 15 else 0
            return int(parsed.timestamp() * 1000) + milliseconds
    number = finite_number(value)
    if number is None:
        return None
    if number > 10_000_000_000:
        return int(number)
    if number > 100_000_000:
        return int(number * 1000)
    return int(number)


def _quote_session(value: Any) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    if len(digits) < 8 or digits[:2] not in {"19", "20"}:
        return ""
    try:
        datetime.strptime(digits[:8], "%Y%m%d")
    except ValueError:
        return ""
    return digits[:8]


class ScreeningSource:
    """Normalize broker objects immediately and retain only bounded JSON-clean rows."""

    def __init__(
        self,
        call_xtdata: Callable[..., Any],
        *,
        broker_id: str = "default",
        capabilities: Iterable[str] | None = None,
        capability_provider: Callable[[], Iterable[str]] | None = None,
        read_bars: Callable[..., dict[str, Any]] | None = None,
    ):
        self.call_xtdata = call_xtdata
        self.broker_id = broker_id
        self.capability_provider = capability_provider
        self.read_bars = read_bars
        self.errors: list[dict[str, Any]] = []
        self.error_count = 0
        self._capabilities = frozenset(
            capabilities
            or {
                "daily_bars",
                "snapshot",
                "instrument_detail",
                "financial_data",
            }
        )

    @property
    def capabilities(self) -> frozenset[str]:
        if self.capability_provider is not None:
            return frozenset(self.capability_provider())
        return self._capabilities

    def _record_error(self, payload: dict[str, Any]) -> None:
        self.error_count += 1
        self.errors.append(payload)
        if len(self.errors) > MAX_SOURCE_ERRORS:
            del self.errors[: len(self.errors) - MAX_SOURCE_ERRORS]

    def data_context(self, *, as_of: str = "", captured_at: str = "") -> DataContext:
        captured = captured_at or datetime.now(UTC).isoformat()
        try:
            captured_session = datetime.fromisoformat(captured).astimezone(MARKET_TIMEZONE).strftime("%Y%m%d")
        except ValueError:
            captured_session = datetime.now(MARKET_TIMEZONE).strftime("%Y%m%d")
        session = as_of or captured_session
        return DataContext(
            captured_at=captured,
            as_of=session,
            market_session=session,
            price_adjustment="front_ratio",
            factor_version=FACTOR_VERSION,
            broker_id=self.broker_id,
            sources=(),
        )

    def daily_bars(
        self,
        codes: list[str],
        *,
        start_time: str = "",
        end_time: str = "",
        count: int = 260,
        dividend_type: str = "front_ratio",
        completed_through: str = "",
    ) -> dict[str, tuple[dict[str, Any], ...]]:
        result: dict[str, tuple[dict[str, Any], ...]] = {code: () for code in codes}
        query_end_time = end_time or completed_through
        for batch in _chunks(codes, 50):
            try:
                if self.read_bars is not None:
                    envelope = self.read_bars(
                        codes=batch,
                        period="1d",
                        fields=DAILY_FIELDS,
                        start_time=start_time,
                        end_time=query_end_time,
                        count=count,
                        dividend_type=dividend_type,
                        fill_data=True,
                        enable_read_from_server=True,
                    )
                    normalized = envelope.get("rows", []) if envelope.get("ok") else []
                else:
                    raw = self.call_xtdata(
                        "get_market_data_ex",
                        DAILY_FIELDS,
                        batch,
                        "1d",
                        start_time,
                        query_end_time,
                        count,
                        dividend_type,
                        True,
                        True,
                    )
                    normalized = bars_rows(raw, batch, DAILY_FIELDS)
                    del raw
            except Exception as exc:
                self._record_error({"source": "daily_bars", "codes": list(batch), "error_type": type(exc).__name__})
                for code in batch:
                    result[code] = ({"code": code, "time": "", "_source_error": type(exc).__name__},)
                continue
            grouped: dict[str, list[dict[str, Any]]] = {code: [] for code in batch}
            for row in normalized:
                code = str(row.get("code") or "")
                time_value = str(row.get("time") or "")
                if code not in grouped or not time_value:
                    continue
                if completed_through and time_value[:8] > completed_through[:8]:
                    continue
                grouped[code].append(dict(row))
            for code, rows in grouped.items():
                result[code] = tuple(sorted(rows, key=lambda row: str(row.get("time") or ""))[-260:])
        return result

    def snapshots(
        self,
        codes: list[str],
        *,
        captured_epoch_ms: int | None = None,
        max_age_seconds: float = 15,
        expected_session: str = "",
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        captured = captured_epoch_ms or int(datetime.now(UTC).timestamp() * 1000)
        for batch in _chunks(codes, 50):
            try:
                raw = self.call_xtdata("get_full_tick", batch)
                records = snapshot_records(raw, batch)
                del raw
            except Exception as exc:
                self._record_error({"source": "snapshot", "codes": list(batch), "error_type": type(exc).__name__})
                for code in batch:
                    result[code] = {"code": code, "missing_reason": "source_error"}
                continue
            for record in records:
                code = str(record.get("code") or "")
                bids = record.get("bid_price") if isinstance(record.get("bid_price"), list) else []
                asks = record.get("ask_price") if isinstance(record.get("ask_price"), list) else []
                bid = finite_number(bids[0]) if bids else None
                ask = finite_number(asks[0]) if asks else None
                quote_ms = _quote_epoch_ms(record.get("time"))
                age = max(0.0, (captured - quote_ms) / 1000) if quote_ms is not None else None
                reason = None
                if not bid or not ask:
                    reason = "one_sided_quote" if record.get("raw_fields") else "missing_source_field"
                elif ask <= bid:
                    reason = "invalid_source_value"
                elif age is None or age > max_age_seconds:
                    reason = "stale_snapshot"
                quote_session = _quote_session(record.get("time"))
                session_mismatch = bool(expected_session and quote_session and quote_session != expected_session[:8])
                if session_mismatch:
                    reason = "stale_snapshot"
                result[code] = {
                    **record,
                    "bid1": bid,
                    "ask1": ask,
                    "quote_age_seconds": age,
                    "session_mismatch": session_mismatch,
                    "missing_reason": reason,
                }
        for code in codes:
            result.setdefault(code, {"code": code, "missing_reason": "missing_source_field"})
        return result

    def financial_tables(
        self,
        codes: list[str],
        tables: list[str],
        *,
        start_time: str = "",
        end_time: str = "",
    ) -> dict[str, dict[str, tuple[dict[str, Any], ...]]]:
        result: dict[str, dict[str, tuple[dict[str, Any], ...]]] = {code: {} for code in codes}
        for batch in _chunks(codes, 200):
            try:
                raw = self.call_xtdata(
                    "get_financial_data",
                    batch,
                    tables,
                    start_time,
                    end_time,
                    "announce_time",
                )
                groups, _truncated = financial_groups(raw, limit=100_000)
                del raw
            except Exception as exc:
                self._record_error({"source": "financial", "codes": list(batch), "error_type": type(exc).__name__})
                for code in batch:
                    result[code] = {"_source_error": ({"error_type": type(exc).__name__},)}
                continue
            for group in groups:
                code = str(group.get("code") or "")
                table = str(group.get("table") or "")
                rows = group.get("rows")
                if code in result and table and isinstance(rows, list):
                    result[code][table] = tuple(dict(row) for row in rows if isinstance(row, dict))
        return result
