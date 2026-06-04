"""Quote subscription store and runtime for 013."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import sleep, time
from typing import Any

from qmt_mcp_core.errors import McpCoreError

from .quote_cache import QuoteHotCache, utc_now_iso
from .serializers import json_clean, snapshot_records

OFFICIAL_BACKEND = "official_subscription"
POLLING_BACKEND = "polling_fallback"
WHOLE_QUOTE_BACKEND = "whole_quote"
DISABLED_BACKEND = "disabled"


@dataclass
class QuoteSubscription:
    id: str
    codes: list[str]
    period: str = "tick"
    backend_preference: str = "auto"
    fallback_polling: bool = True
    fallback_interval_seconds: int = 5
    enabled: bool = True
    label: str = ""
    group: str = ""
    notes: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    active_backend: str = DISABLED_BACKEND
    xtdata_subscription_ids: dict[str, int] = field(default_factory=dict)
    last_update_at: str = ""
    last_error: str = ""
    fallback_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> QuoteSubscription:
        allowed = {field.name for field in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        data = {key: value for key, value in raw.items() if key in allowed}
        return cls(**data)


class QuoteSubscriptionStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._items: dict[str, QuoteSubscription] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._items = {}
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        items = raw.get("subscriptions", raw if isinstance(raw, list) else [])
        self._items = {item["id"]: QuoteSubscription.from_dict(item) for item in items}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": "quote-subscriptions-v1", "subscriptions": [s.to_dict() for s in self.list()]}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def upsert(self, sub: QuoteSubscription) -> QuoteSubscription:
        existing = self._items.get(sub.id)
        if existing:
            sub.created_at = existing.created_at
        sub.updated_at = utc_now_iso()
        self._items[sub.id] = sub
        self.save()
        return sub

    def remove(self, subscription_id: str) -> QuoteSubscription:
        try:
            sub = self._items.pop(subscription_id)
        except KeyError as exc:
            raise McpCoreError("validation", f"unknown subscription: {subscription_id}") from exc
        self.save()
        return sub

    def get(self, subscription_id: str) -> QuoteSubscription | None:
        return self._items.get(subscription_id)

    def list(self) -> list[QuoteSubscription]:
        return sorted(self._items.values(), key=lambda item: item.id)


class QuoteSubscriptionRuntime:
    def __init__(
        self,
        *,
        store: QuoteSubscriptionStore,
        cache: QuoteHotCache,
        xtdata_call: Callable[..., Any],
        max_official: int = 50,
    ):
        self.store = store
        self.cache = cache
        self.xtdata_call = xtdata_call
        self.max_official = max_official
        self._fallback_thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start_fallback_worker(self, *, poll_seconds: float = 1.0) -> None:
        if self._fallback_thread and self._fallback_thread.is_alive():
            return

        def run() -> None:
            while not self._stop.wait(poll_seconds):
                try:
                    self.refresh_fallback_due()
                except Exception:
                    # Per-subscription diagnostics are updated by refresh paths.
                    sleep(min(poll_seconds, 1.0))

        self._fallback_thread = threading.Thread(target=run, name="qmt-quote-fallback", daemon=True)
        self._fallback_thread.start()

    def stop_fallback_worker(self) -> None:
        self._stop.set()

    def subscribe(self, sub: QuoteSubscription) -> QuoteSubscription:
        self._unsubscribe_existing(sub.id)
        if not sub.enabled:
            sub.active_backend = DISABLED_BACKEND
            return self.store.upsert(sub)
        if sub.backend_preference != POLLING_BACKEND:
            try:
                self._register_official(sub)
                return self.store.upsert(sub)
            except McpCoreError as exc:
                if not sub.fallback_polling:
                    raise
                sub.fallback_reason = exc.message
                sub.last_error = exc.message
        if sub.fallback_polling:
            sub.active_backend = POLLING_BACKEND
            self.refresh_fallback(sub)
            return self.store.upsert(sub)
        sub.active_backend = DISABLED_BACKEND
        return self.store.upsert(sub)

    def unsubscribe(self, subscription_id: str) -> QuoteSubscription:
        sub = self.store.remove(subscription_id)
        self._unsubscribe_xtdata(sub)
        sub.enabled = False
        sub.active_backend = DISABLED_BACKEND
        sub.updated_at = utc_now_iso()
        return sub

    def status(self) -> dict[str, Any]:
        subs = self.store.list()
        return {
            "enabled": any(s.enabled for s in subs),
            "subscription_count": len(subs),
            "code_count": len({code for sub in subs if sub.enabled for code in sub.codes}),
            "backends": sorted({sub.active_backend for sub in subs}),
            "subscriptions": [sub.to_dict() for sub in subs],
            "cache": self.cache.status(),
        }

    def refresh_fallback_due(self) -> None:
        now = time()
        for sub in self.store.list():
            if not (sub.enabled and sub.fallback_polling and sub.active_backend == POLLING_BACKEND):
                continue
            if (
                not sub.last_update_at
                or self._age_seconds(sub.last_update_at, now=now) >= sub.fallback_interval_seconds
            ):
                self.refresh_fallback(sub)
                self.store.upsert(sub)

    def refresh_fallback(self, sub: QuoteSubscription) -> None:
        raw = self.xtdata_call("get_full_tick", sub.codes)
        self.cache.put_xtdata_raw(raw, sub.codes, source=POLLING_BACKEND)
        sub.last_update_at = utc_now_iso()
        sub.last_error = ""

    def _register_official(self, sub: QuoteSubscription) -> None:
        if len(sub.codes) > self.max_official:
            raise McpCoreError("capacity", "too many official quote subscriptions", {"max": self.max_official})
        sub.xtdata_subscription_ids = {}

        def callback(raw: Any, *, codes: list[str] | None = None) -> None:
            self._handle_callback(sub.id, raw, codes=codes)

        for code in sub.codes:
            subscription_id = self._subscribe_quote(code, sub.period, callback)
            sub.xtdata_subscription_ids[code] = int(subscription_id) if subscription_id is not None else 0
        sub.active_backend = OFFICIAL_BACKEND
        sub.last_update_at = utc_now_iso()
        sub.last_error = ""
        sub.fallback_reason = ""

    def _handle_callback(self, subscription_id: str, raw: Any, *, codes: list[str] | None = None) -> None:
        sub = self.store.get(subscription_id)
        if sub is None:
            return
        clean = json_clean(raw)
        if isinstance(clean, dict) and any(code in clean for code in sub.codes):
            records = snapshot_records(clean, sub.codes)
        elif codes:
            records = snapshot_records(clean, codes)
        elif len(sub.codes) == 1:
            records = snapshot_records({sub.codes[0]: clean}, sub.codes)
        else:
            records = []
        for record in records:
            self.cache.put_snapshot(record["code"], record, source=OFFICIAL_BACKEND)
        sub.last_update_at = utc_now_iso()
        sub.last_error = ""
        self.store.upsert(sub)

    def _unsubscribe_existing(self, subscription_id: str) -> None:
        existing = self.store.get(subscription_id)
        if existing:
            self._unsubscribe_xtdata(existing)

    def _unsubscribe_xtdata(self, sub: QuoteSubscription) -> None:
        for sid in sub.xtdata_subscription_ids.values():
            if sid:
                try:
                    self.xtdata_call("unsubscribe_quote", sid)
                except McpCoreError as exc:
                    sub.last_error = exc.message

    def _subscribe_quote(self, code: str, period: str, callback) -> Any:
        try:
            return self.xtdata_call("subscribe_quote", code, period, "", 0, callback)
        except McpCoreError as exc:
            if "TypeError" not in exc.message and "takes" not in exc.message and "positional" not in exc.message:
                raise
        return self.xtdata_call("subscribe_quote", code, period, 0, callback)

    @staticmethod
    def _age_seconds(iso_value: str, *, now: float) -> float:
        # Used only as a coarse fallback throttle; malformed values refresh now.
        try:
            from datetime import datetime

            return now - datetime.fromisoformat(iso_value).timestamp()
        except Exception:
            return 999999.0
