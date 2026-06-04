"""Latest-only formula callback cache."""

from __future__ import annotations

from time import time
from typing import Any

from .quote_cache import utc_now_iso
from .serializers import json_clean


class FormulaCache:
    def __init__(self):
        self._items: dict[str, dict[str, Any]] = {}

    def put(self, key: str, payload: Any) -> None:
        self._items[key] = {"key": key, "payload": json_clean(payload), "cached_at": utc_now_iso(), "monotonic": time()}

    def status(self) -> dict[str, Any]:
        now = time()
        return {
            "entry_count": len(self._items),
            "entries": [
                {k: v for k, v in item.items() if k != "monotonic"} | {"age_ms": int((now - item["monotonic"]) * 1000)}
                for item in self._items.values()
            ],
        }
