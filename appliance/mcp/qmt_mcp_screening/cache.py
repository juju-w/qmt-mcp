"""Lock-protected bounded TTL/LRU caches for screening."""

from __future__ import annotations

import json
import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from qmt_mcp_core.errors import McpCoreError

K = TypeVar("K")
V = TypeVar("V")


class BoundedTTLCache(Generic[K, V]):  # noqa: UP046 - Windows release remains Python 3.11
    def __init__(
        self,
        *,
        max_items: int,
        ttl_seconds: float,
        max_bytes: int = 0,
        size_fn: Callable[[V], int] | None = None,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        if max_items < 1 or ttl_seconds <= 0 or max_bytes < 0:
            raise ValueError("invalid cache bounds")
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self.max_bytes = max_bytes
        self.size_fn = size_fn or (lambda _value: 0)
        self.time_fn = time_fn
        self._items: OrderedDict[K, tuple[float, V, int]] = OrderedDict()
        self._bytes = 0
        self._lock = threading.RLock()

    @property
    def payload_bytes(self) -> int:
        with self._lock:
            return self._bytes

    def _remove(self, key: K) -> None:
        item = self._items.pop(key, None)
        if item is not None:
            self._bytes -= item[2]

    def _prune_expired(self, now: float) -> None:
        expired = [key for key, (expires, _value, _size) in self._items.items() if expires <= now]
        for key in expired:
            self._remove(key)

    def put(self, key: K, value: V, *, ttl_seconds: float | None = None) -> None:
        size = max(0, int(self.size_fn(value)))
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        if self.max_bytes and size > self.max_bytes:
            raise McpCoreError(
                "capacity",
                "cache item exceeds payload budget",
                {"item_bytes": size, "max_bytes": self.max_bytes},
            )
        with self._lock:
            now = self.time_fn()
            self._prune_expired(now)
            self._remove(key)
            while self._items and (
                len(self._items) >= self.max_items or (self.max_bytes and self._bytes + size > self.max_bytes)
            ):
                oldest = next(iter(self._items))
                self._remove(oldest)
            self._items[key] = (now + ttl, value, size)
            self._bytes += size

    def get(self, key: K) -> V | None:
        with self._lock:
            now = self.time_fn()
            self._prune_expired(now)
            item = self._items.get(key)
            if item is None:
                return None
            self._items.move_to_end(key)
            return item[1]

    def __len__(self) -> int:
        with self._lock:
            self._prune_expired(self.time_fn())
            return len(self._items)


class FactorObservationCache:
    def __init__(
        self,
        *,
        max_items: int = 50_000,
        ttl_seconds: float = 3600,
        snapshot_ttl_seconds: float = 5,
        negative_ttl_seconds: float = 60,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self.ttl_seconds = ttl_seconds
        self.snapshot_ttl_seconds = snapshot_ttl_seconds
        self.negative_ttl_seconds = negative_ttl_seconds
        self._cache = BoundedTTLCache(max_items=max_items, ttl_seconds=ttl_seconds, time_fn=time_fn)

    def get(self, key: tuple) -> Any | None:
        return self._cache.get(key)

    def put(self, key: tuple, value: Any, *, freshness: str = "completed_daily") -> None:
        status = getattr(value, "status", "available")
        if status != "available":
            ttl = self.negative_ttl_seconds
        elif freshness == "snapshot":
            ttl = self.snapshot_ttl_seconds
        else:
            ttl = self.ttl_seconds
        self._cache.put(key, value, ttl_seconds=ttl)


class ScreenResultStore:
    def __init__(
        self,
        *,
        max_items: int = 100,
        max_bytes: int = 67_108_864,
        ttl_seconds: float = 900,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self.ttl_seconds = ttl_seconds
        self._cache: BoundedTTLCache[str, bytes] = BoundedTTLCache(
            max_items=max_items,
            max_bytes=max_bytes,
            ttl_seconds=ttl_seconds,
            size_fn=len,
            time_fn=time_fn,
        )

    @property
    def payload_bytes(self) -> int:
        return self._cache.payload_bytes

    def put(self, payload: dict[str, Any]) -> str:
        screen_id = f"scr_{secrets.token_hex(16)}"
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self._cache.put(screen_id, encoded)
        return screen_id

    def get(self, screen_id: str) -> dict[str, Any] | None:
        encoded = self._cache.get(screen_id)
        if encoded is None:
            return None
        return json.loads(encoded.decode("utf-8"))
