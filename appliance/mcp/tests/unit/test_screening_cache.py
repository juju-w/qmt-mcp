from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from qmt_mcp_screening.cache import BoundedTTLCache, FactorObservationCache, ScreenResultStore
from qmt_mcp_screening.models import FactorObservation


def test_ttl_and_lru_evict_deterministically():
    now = [100.0]
    cache = BoundedTTLCache(max_items=2, ttl_seconds=10, time_fn=lambda: now[0])
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.get("b") is None
    now[0] = 111.0
    assert cache.get("a") is None


def test_screen_result_store_enforces_payload_budget_and_immutability():
    store = ScreenResultStore(max_items=10, max_bytes=80, ttl_seconds=60)
    first = store.put({"value": "a" * 20})
    loaded = store.get(first)
    loaded["value"] = "changed"
    assert store.get(first)["value"] == "a" * 20
    second = store.put({"value": "b" * 40})
    assert store.get(second)["value"] == "b" * 40
    assert store.payload_bytes <= 80


def test_screen_result_ids_are_opaque_and_prefixed():
    store = ScreenResultStore(max_items=2, max_bytes=1000, ttl_seconds=60)
    one = store.put({"value": 1})
    two = store.put({"value": 2})
    assert one.startswith("scr_")
    assert len(one) > 20
    assert one != two


def test_screen_result_store_expires_and_evicts_by_count_under_concurrent_reads():
    now = [100.0]
    store = ScreenResultStore(max_items=2, max_bytes=10_000, ttl_seconds=10, time_fn=lambda: now[0])
    first = store.put({"candidates": {"A": {"state": "selected"}, "B": {"state": "rejected"}}})
    second = store.put({"value": 2})
    with ThreadPoolExecutor(max_workers=4) as pool:
        states = list(pool.map(lambda _index: store.get(first)["candidates"]["B"]["state"], range(20)))
    assert states == ["rejected"] * 20
    third = store.put({"value": 3})
    assert store.get(second) is None
    assert store.get(first)["candidates"]["A"]["state"] == "selected"
    assert store.get(third)["value"] == 3
    now[0] = 111
    assert store.get(first) is None


def test_factor_cache_uses_short_snapshot_and_negative_ttls():
    now = [100.0]
    cache = FactorObservationCache(
        ttl_seconds=60,
        snapshot_ttl_seconds=5,
        negative_ttl_seconds=2,
        time_fn=lambda: now[0],
    )
    stable = FactorObservation.available(code="A", factor_id="return", params={}, value=0.1, unit="ratio")
    snapshot = FactorObservation.available(code="A", factor_id="bid_ask_spread_bps", params={}, value=2.0, unit="bps")
    missing = FactorObservation.missing(code="A", factor_id="roe_ttm", params={}, reason="source_error", unit="ratio")
    cache.put(("stable",), stable)
    cache.put(("snapshot",), snapshot, freshness="snapshot")
    cache.put(("missing",), missing, freshness="announced_financial")

    now[0] = 103.0
    assert cache.get(("stable",)) is stable
    assert cache.get(("snapshot",)) is snapshot
    assert cache.get(("missing",)) is None
    now[0] = 106.0
    assert cache.get(("stable",)) is stable
    assert cache.get(("snapshot",)) is None
