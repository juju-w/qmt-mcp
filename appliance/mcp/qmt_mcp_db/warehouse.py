"""Market-data warehouse: bars upsert / read / coverage (012).

broker_id-namespaced. Uses the sync DbEngine facade. Pure mapping is in rows.py.
"""

from __future__ import annotations

from typing import Any

from .rows import OHLCV, from_record, to_records

_UPSERT = """
INSERT INTO md_bars (broker_id, code, period, dividend_type, dt, open, high, low, close, volume, amount, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now())
ON CONFLICT (broker_id, code, period, dividend_type, dt) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
    volume = EXCLUDED.volume, amount = EXCLUDED.amount, updated_at = now()
"""


class Warehouse:
    def __init__(self, engine, broker_id: str):
        self.engine = engine
        self.broker_id = broker_id

    def upsert_bars(self, code: str, period: str, dividend_type: str, rows: list[dict[str, Any]]) -> int:
        recs = to_records(self.broker_id, code, period, dividend_type, rows)
        if not recs:
            return 0
        args = [
            (
                r["broker_id"],
                r["code"],
                r["period"],
                r["dividend_type"],
                r["dt"],
                r["open"],
                r["high"],
                r["low"],
                r["close"],
                r["volume"],
                r["amount"],
            )
            for r in recs
        ]
        self.engine.executemany(_UPSERT, args)
        return len(recs)

    def coverage(self, code: str, period: str, dividend_type: str) -> dict[str, Any]:
        rows = self.engine.fetch(
            "SELECT min(dt) AS mn, max(dt) AS mx, count(*) AS n FROM md_bars "
            "WHERE broker_id = $1 AND code = $2 AND period = $3 AND dividend_type = $4",
            self.broker_id,
            code,
            period,
            dividend_type,
        )
        r = rows[0] if rows else {}
        return {"min": r.get("mn"), "max": r.get("mx"), "count": int(r.get("n") or 0)}

    def read_bars(
        self, code: str, period: str, dividend_type: str, start: str = "", end: str = ""
    ) -> list[dict[str, Any]]:
        sql = (
            "SELECT code, dt, " + ", ".join(OHLCV) + " FROM md_bars "
            "WHERE broker_id = $1 AND code = $2 AND period = $3 AND dividend_type = $4"
        )
        args: list[Any] = [self.broker_id, code, period, dividend_type]
        if start:
            args.append(start)
            sql += f" AND dt >= ${len(args)}"
        if end:
            args.append(end)
            sql += f" AND dt <= ${len(args)}"
        sql += " ORDER BY dt"
        return [from_record(r) for r in self.engine.fetch(sql, *args)]
