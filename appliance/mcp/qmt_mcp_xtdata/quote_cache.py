"""Latest-only quote hot cache for 013 subscriptions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import time
from typing import Any

from .serializers import json_clean, snapshot_records


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class QuoteCacheEntry:
    broker_id: str
    code: str
    snapshot: dict[str, Any]
    source: str
    cached_at: str
    cached_at_monotonic: float

    def age_ms(self, now: float | None = None) -> int:
        current = time() if now is None else now
        return max(0, int((current - self.cached_at_monotonic) * 1000))

    def to_record(self, *, now: float | None = None) -> dict[str, Any]:
        return {
            "broker_id": self.broker_id,
            "code": self.code,
            "snapshot": self.snapshot,
            "source": self.source,
            "cached_at": self.cached_at,
            "age_ms": self.age_ms(now),
        }


class QuoteHotCache:
    def __init__(self, broker_id: str, default_max_age_ms: int = 10_000):
        self.broker_id = broker_id
        self.default_max_age_ms = default_max_age_ms
        self._entries: dict[str, QuoteCacheEntry] = {}

    def put_snapshot(self, code: str, snapshot: dict[str, Any], *, source: str) -> QuoteCacheEntry:
        entry = QuoteCacheEntry(
            broker_id=self.broker_id,
            code=code,
            snapshot=json_clean(snapshot) if isinstance(snapshot, dict) else {"value": json_clean(snapshot)},
            source=source,
            cached_at=utc_now_iso(),
            cached_at_monotonic=time(),
        )
        self._entries[code] = entry
        return entry

    def put_xtdata_raw(self, raw: Any, codes: list[str], *, source: str) -> list[QuoteCacheEntry]:
        return [self.put_snapshot(record["code"], record, source=source) for record in snapshot_records(raw, codes)]

    def get(self, code: str) -> QuoteCacheEntry | None:
        return self._entries.get(code)

    def fresh_records(
        self, codes: list[str], *, max_age_ms: int | None = None
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        threshold = self.default_max_age_ms if max_age_ms is None else max_age_ms
        records: list[dict[str, Any]] = []
        missing: list[str] = []
        stale: list[str] = []
        now = time()
        for code in codes:
            entry = self._entries.get(code)
            if entry is None:
                missing.append(code)
                continue
            record = entry.to_record(now=now)
            if record["age_ms"] > threshold:
                stale.append(code)
                continue
            records.append(record)
        return records, missing, stale

    def status(self) -> dict[str, Any]:
        now = time()
        return {
            "broker_id": self.broker_id,
            "entry_count": len(self._entries),
            "default_max_age_ms": self.default_max_age_ms,
            "entries": [
                {"code": code, "source": entry.source, "cached_at": entry.cached_at, "age_ms": entry.age_ms(now)}
                for code, entry in sorted(self._entries.items())
            ],
        }
