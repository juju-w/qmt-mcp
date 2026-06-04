from __future__ import annotations

from qmt_mcp_xtdata.quote_cache import QuoteHotCache


def test_quote_cache_latest_only_and_freshness():
    cache = QuoteHotCache("acme", default_max_age_ms=1000)
    cache.put_snapshot("510300.SH", {"code": "510300.SH", "last_price": 4.0}, source="test")
    cache.put_snapshot("510300.SH", {"code": "510300.SH", "last_price": 4.1}, source="test")

    records, missing, stale = cache.fresh_records(["510300.SH"])
    assert missing == []
    assert stale == []
    assert records[0]["snapshot"]["last_price"] == 4.1
    assert cache.status()["entry_count"] == 1


def test_quote_cache_missing_and_stale():
    cache = QuoteHotCache("acme", default_max_age_ms=1)
    entry = cache.put_snapshot("510300.SH", {"code": "510300.SH"}, source="test")
    entry.cached_at_monotonic -= 10

    records, missing, stale = cache.fresh_records(["510300.SH", "510500.SH"])
    assert records == []
    assert missing == ["510500.SH"]
    assert stale == ["510300.SH"]


def test_quote_cache_put_xtdata_raw_uses_snapshot_serializer():
    cache = QuoteHotCache("acme")
    cache.put_xtdata_raw({"510300.SH": {"lastPrice": 4.2}}, ["510300.SH"], source="raw")
    record = cache.get("510300.SH").to_record()  # type: ignore[union-attr]
    assert record["snapshot"]["last_price"] == 4.2
    assert record["source"] == "raw"
