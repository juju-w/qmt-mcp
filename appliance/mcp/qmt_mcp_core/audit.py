"""Append-only JSONL audit logging."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .errors import McpCoreError

SECRET_RE = re.compile(r"(token|password|passwd|secret|cookie|captcha|credential)", re.I)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def request_id() -> str:
    return f"req_{uuid.uuid4().hex[:16]}"


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in list(value.items())[:30]}
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        return {
            "count": len(items),
            "sample": [_jsonable(v) for v in items[:5]],
            "truncated": len(items) > 5,
        }
    return str(value)


def sanitize_args(args: dict[str, Any] | None) -> dict[str, Any]:
    if not args:
        return {}
    clean: dict[str, Any] = {}
    for key, value in args.items():
        if SECRET_RE.search(str(key)):
            clean[key] = "<redacted>"
        else:
            clean[key] = _jsonable(value)
    return clean


class JsonlAuditSink:
    def __init__(self, path: str, broker_id: str):
        self.path = Path(path)
        self.broker_id = broker_id
        self._lock = threading.Lock()

    def initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8"):
                pass
        except Exception as exc:
            raise McpCoreError(
                "persistence",
                f"audit sink is not writable: {self.path}",
                {"cause": f"{type(exc).__name__}: {exc}"},
            ) from exc

    def append(
        self,
        *,
        request_id_value: str,
        tool: str,
        family: str,
        args_summary: dict[str, Any] | None,
        outcome: str,
        latency_ms: int,
        error_type: str | None = None,
        account_id: str | None = None,
    ) -> None:
        record = {
            "ts": now_iso(),
            "request_id": request_id_value,
            "broker_id": self.broker_id,
            "tool": tool,
            "family": family,
            "account_id": account_id,
            "args_summary": sanitize_args(args_summary),
            "outcome": outcome,
            "error_type": error_type,
            "latency_ms": latency_ms,
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        try:
            with self._lock:
                fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
                try:
                    os.write(fd, (line + "\n").encode("utf-8"))
                finally:
                    os.close(fd)
        except Exception as exc:
            raise McpCoreError(
                "persistence",
                "failed to append audit record",
                {"cause": f"{type(exc).__name__}: {exc}"},
            ) from exc
