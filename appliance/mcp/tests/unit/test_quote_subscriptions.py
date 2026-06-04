from __future__ import annotations

import json

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_xtdata.quote_cache import QuoteHotCache
from qmt_mcp_xtdata.quote_subscriptions import (
    OFFICIAL_BACKEND,
    POLLING_BACKEND,
    QuoteSubscription,
    QuoteSubscriptionRuntime,
    QuoteSubscriptionStore,
)


class FakeXtdata:
    def __init__(self):
        self.calls = []
        self.callbacks = {}
        self.next_id = 100
        self.fail_subscribe = False

    def call(self, name, *args):
        self.calls.append((name, args))
        if name == "subscribe_quote":
            if self.fail_subscribe:
                raise McpCoreError("dependency", "xtdata.subscribe_quote failed: not supported")
            sid = self.next_id
            self.next_id += 1
            self.callbacks[sid] = args[-1]
            return sid
        if name == "unsubscribe_quote":
            return True
        if name == "get_full_tick":
            return {code: {"lastPrice": 10.0 + i} for i, code in enumerate(args[0])}
        raise McpCoreError("dependency", f"unknown {name}")


def test_store_persists_subscriptions(tmp_path):
    store = QuoteSubscriptionStore(tmp_path / "subs.json")
    store.upsert(QuoteSubscription(id="s1", codes=["510300.SH"], label="one"))

    loaded = QuoteSubscriptionStore(tmp_path / "subs.json")
    assert loaded.get("s1").codes == ["510300.SH"]  # type: ignore[union-attr]
    raw = json.loads((tmp_path / "subs.json").read_text())
    assert raw["schema"] == "quote-subscriptions-v1"


def test_official_subscription_callback_updates_cache(tmp_path):
    fake = FakeXtdata()
    store = QuoteSubscriptionStore(tmp_path / "subs.json")
    cache = QuoteHotCache("acme")
    runtime = QuoteSubscriptionRuntime(store=store, cache=cache, xtdata_call=fake.call)

    saved = runtime.subscribe(QuoteSubscription(id="s1", codes=["510300.SH"]))
    assert saved.active_backend == OFFICIAL_BACKEND
    sid = saved.xtdata_subscription_ids["510300.SH"]

    fake.callbacks[sid]({"lastPrice": 4.2})
    entry = cache.get("510300.SH")
    assert entry is not None
    assert entry.snapshot["last_price"] == 4.2

    runtime.unsubscribe("s1")
    assert any(call[0] == "unsubscribe_quote" for call in fake.calls)


def test_subscribe_falls_back_to_polling_when_official_unavailable(tmp_path):
    fake = FakeXtdata()
    fake.fail_subscribe = True
    store = QuoteSubscriptionStore(tmp_path / "subs.json")
    cache = QuoteHotCache("acme")
    runtime = QuoteSubscriptionRuntime(store=store, cache=cache, xtdata_call=fake.call)

    saved = runtime.subscribe(QuoteSubscription(id="s1", codes=["510300.SH"], fallback_interval_seconds=5))
    assert saved.active_backend == POLLING_BACKEND
    assert saved.fallback_reason
    assert cache.get("510300.SH").snapshot["last_price"] == 10.0  # type: ignore[union-attr]


def test_unsubscribe_unknown_refuses(tmp_path):
    runtime = QuoteSubscriptionRuntime(
        store=QuoteSubscriptionStore(tmp_path / "subs.json"),
        cache=QuoteHotCache("acme"),
        xtdata_call=FakeXtdata().call,
    )
    with pytest.raises(McpCoreError):
        runtime.unsubscribe("missing")
