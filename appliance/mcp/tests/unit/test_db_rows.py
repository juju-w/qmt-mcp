"""Unit tests for bars<->warehouse row mappers (feature 012)."""

from __future__ import annotations

from qmt_mcp_db.rows import from_record, to_record, to_records


def test_to_record_maps_and_coerces():
    row = {"code": "600000.SH", "time": "20250101", "open": "10.0", "close": 10.5, "volume": 1000}
    rec = to_record("acme", "600000.SH", "1d", "none", row)
    assert rec["broker_id"] == "acme"
    assert rec["code"] == "600000.SH"
    assert rec["dt"] == "20250101"
    assert rec["open"] == 10.0  # str coerced to float
    assert rec["high"] is None  # missing -> None
    assert rec["volume"] == 1000.0


def test_to_records_skips_rows_without_dt():
    rows = [{"code": "x", "time": "20250101", "close": 1}, {"code": "x", "close": 2}]
    recs = to_records("acme", "x", "1d", "none", rows)
    assert len(recs) == 1


def test_from_record_roundtrip_shape():
    rec = to_record("acme", "600000.SH", "1d", "none", {"time": "20250101", "close": 10.5})
    out = from_record(rec)
    assert out["code"] == "600000.SH"
    assert out["time"] == "20250101"
    assert out["close"] == 10.5
    assert set(["open", "high", "low", "close", "volume", "amount"]).issubset(out)
