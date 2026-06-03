"""Unit tests for xtdata output serializers."""

from __future__ import annotations

from datetime import datetime

from qmt_mcp_xtdata import serializers as s


class _FakeNumpyScalar:
    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value


def test_json_clean_primitives_and_datetime():
    assert s.json_clean(1) == 1
    assert s.json_clean("x") == "x"
    assert s.json_clean(None) is None
    dt = datetime(2025, 1, 1, 9, 30, 0)
    assert s.json_clean(dt) == dt.isoformat()


def test_json_clean_numpy_like_scalar():
    assert s.json_clean(_FakeNumpyScalar(3.5)) == 3.5


def test_json_clean_nested_containers():
    assert s.json_clean({"a": (1, 2)}) == {"a": [1, 2]}


def test_snapshot_records_maps_fields():
    raw = {
        "600000.SH": {
            "lastPrice": 10.5,
            "open": 10.0,
            "preClose": 9.8,
            "volume": 1000,
            "time": "093000",
        }
    }
    records = s.snapshot_records(raw, ["600000.SH"])
    assert len(records) == 1
    rec = records[0]
    assert rec["code"] == "600000.SH"
    assert rec["last_price"] == 10.5
    assert rec["pre_close"] == 9.8
    assert rec["raw_fields"]["volume"] == 1000


def test_snapshot_records_missing_code_is_empty():
    records = s.snapshot_records({}, ["000001.SZ"])
    assert records[0]["code"] == "000001.SZ"
    assert records[0]["last_price"] is None


def test_bars_rows_field_outer_shape():
    raw = {"close": {"20250101": {"600000.SH": 10.0}}}
    rows = s.bars_rows(raw, ["600000.SH"], ["close"])
    assert rows == [{"code": "600000.SH", "time": "20250101", "close": 10.0}]


def test_bars_rows_code_outer_shape():
    raw = {"600000.SH": {"close": {"20250101": 11.0}}}
    rows = s.bars_rows(raw, ["600000.SH"], ["close"])
    assert rows == [{"code": "600000.SH", "time": "20250101", "close": 11.0}]


def test_date_strings_from_list_and_int():
    assert s.date_strings(["20250101", "20250102"]) == ["20250101", "20250102"]
    assert s.date_strings(20250101) == ["20250101"]
