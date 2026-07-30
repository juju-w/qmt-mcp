"""Dependency-light durable state for the stable MCP Tasks extension."""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACTIVE_STATUSES = ("working", "input_required")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")
ALL_STATUSES = frozenset((*ACTIVE_STATUSES, *TERMINAL_STATUSES))
TASK_ID_PATTERN = re.compile(r"^tsk_[A-Za-z0-9_-]{32,64}$")
MAX_STATUS_MESSAGE = 512


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _utc_timestamp(epoch_ms: int) -> str:
    value = datetime.fromtimestamp(epoch_ms / 1000, tz=UTC)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    owner_digest: str
    tool_name: str
    required_scopes: tuple[str, ...]
    status: str
    status_message: str | None
    created_at: str
    updated_at: str
    expires_at_ms: int | None
    ttl_ms: int | None
    poll_interval_ms: int
    result: Any | None
    error: dict[str, Any] | None
    input_requests: dict[str, Any] | None

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def to_wire(self, *, created: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "resultType": "task" if created else "complete",
            "taskId": self.task_id,
            "status": self.status,
            "createdAt": self.created_at,
            "lastUpdatedAt": self.updated_at,
            "ttlMs": self.ttl_ms,
            "pollIntervalMs": self.poll_interval_ms,
        }
        if self.status_message:
            payload["statusMessage"] = self.status_message
        if created:
            return payload
        if self.status == "completed" and self.result is not None:
            payload["result"] = self.result
        elif self.status == "failed" and self.error is not None:
            payload["error"] = self.error
        elif self.status == "input_required" and self.input_requests is not None:
            payload["inputRequests"] = self.input_requests
        return payload


class TaskStore:
    """SQLite-backed task records with atomic, terminal-safe transitions."""

    def __init__(
        self,
        path: str | Path,
        *,
        ttl_ms: int = 86_400_000,
        poll_interval_ms: int = 1000,
        max_retained: int = 1000,
        clock_ms: Callable[[], int] | None = None,
    ):
        self.path = Path(path)
        self.ttl_ms = ttl_ms
        self.poll_interval_ms = poll_interval_ms
        self.max_retained = max_retained
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._initialize()

    @staticmethod
    def valid_task_id(task_id: str) -> bool:
        return bool(TASK_ID_PATTERN.fullmatch(task_id or ""))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_store_schema (
                    version INTEGER PRIMARY KEY
                );
                INSERT OR IGNORE INTO task_store_schema(version) VALUES (1);

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    owner_digest TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    required_scopes_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('working', 'input_required', 'completed', 'failed', 'cancelled')
                    ),
                    status_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at_ms INTEGER,
                    ttl_ms INTEGER,
                    poll_interval_ms INTEGER NOT NULL,
                    result_json TEXT,
                    error_json TEXT,
                    input_requests_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_status_updated
                    ON tasks(status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_expiry
                    ON tasks(expires_at_ms);
                """
            )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def create(self, *, owner_digest: str, tool_name: str, required_scopes: tuple[str, ...]) -> TaskRecord:
        if len(owner_digest) != 64 or len(tool_name) > 128:
            raise ValueError("invalid task owner or tool")
        scopes = tuple(sorted(set(required_scopes)))
        if len(scopes) > 32 or any(not scope or len(scope) > 128 for scope in scopes):
            raise ValueError("invalid task scopes")
        now_ms = self._clock_ms()
        now = _utc_timestamp(now_ms)
        expires_at_ms = now_ms + self.ttl_ms if self.ttl_ms > 0 else None
        ttl_ms = self.ttl_ms if self.ttl_ms > 0 else None
        for _ in range(3):
            task_id = "tsk_" + secrets.token_urlsafe(32)
            try:
                with self._connect() as connection:
                    connection.execute(
                        """
                        INSERT INTO tasks (
                            task_id, owner_digest, tool_name, required_scopes_json,
                            status, created_at, updated_at, expires_at_ms, ttl_ms,
                            poll_interval_ms
                        ) VALUES (?, ?, ?, ?, 'working', ?, ?, ?, ?, ?)
                        """,
                        (
                            task_id,
                            owner_digest,
                            tool_name,
                            _compact_json(scopes),
                            now,
                            now,
                            expires_at_ms,
                            ttl_ms,
                            self.poll_interval_ms,
                        ),
                    )
                record = self.get(task_id)
                assert record is not None
                return record
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("could not allocate a unique task id")

    def get(self, task_id: str) -> TaskRecord | None:
        if not self.valid_task_id(task_id):
            return None
        now_ms = self._clock_ms()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            if row["expires_at_ms"] is not None and row["expires_at_ms"] <= now_ms:
                connection.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                return None
        return self._from_row(row)

    def complete(self, task_id: str, result: Any, *, status_message: str | None = None) -> bool:
        return self._transition(
            task_id,
            "completed",
            status_message=status_message,
            result_json=_compact_json(result),
        )

    def fail(self, task_id: str, error: dict[str, Any], *, status_message: str | None = None) -> bool:
        return self._transition(
            task_id,
            "failed",
            status_message=status_message,
            error_json=_compact_json(error),
        )

    def request_input(
        self,
        task_id: str,
        input_requests: dict[str, Any],
        *,
        status_message: str | None = None,
    ) -> bool:
        return self._transition(
            task_id,
            "input_required",
            source_statuses=("working",),
            status_message=status_message,
            input_requests_json=_compact_json(input_requests),
        )

    def replace_input_requests(
        self,
        task_id: str,
        input_requests: dict[str, Any],
        *,
        status_message: str | None = None,
    ) -> bool:
        """Replace a waiting task's pending snapshot without resuming it."""

        if not input_requests or not self.valid_task_id(task_id):
            return False
        safe_message = (status_message or "")[:MAX_STATUS_MESSAGE] or None
        now = _utc_timestamp(self._clock_ms())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks SET
                    status_message = ?,
                    updated_at = ?,
                    input_requests_json = ?
                WHERE task_id = ? AND status = 'input_required'
                """,
                (
                    safe_message,
                    now,
                    _compact_json(input_requests),
                    task_id,
                ),
            )
        return cursor.rowcount == 1

    def resume(self, task_id: str, *, status_message: str | None = None) -> bool:
        return self._transition(
            task_id,
            "working",
            source_statuses=("input_required",),
            status_message=status_message,
        )

    def cancel(self, task_id: str, *, status_message: str | None = "Cancelled by client") -> bool:
        return self._transition(task_id, "cancelled", status_message=status_message)

    def _transition(
        self,
        task_id: str,
        status: str,
        *,
        source_statuses: tuple[str, ...] = ACTIVE_STATUSES,
        status_message: str | None = None,
        result_json: str | None = None,
        error_json: str | None = None,
        input_requests_json: str | None = None,
    ) -> bool:
        if status not in ALL_STATUSES or not self.valid_task_id(task_id):
            return False
        safe_message = (status_message or "")[:MAX_STATUS_MESSAGE] or None
        now = _utc_timestamp(self._clock_ms())
        placeholders = ",".join("?" for _ in source_statuses)
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE tasks SET
                    status = ?,
                    status_message = ?,
                    updated_at = ?,
                    result_json = ?,
                    error_json = ?,
                    input_requests_json = ?
                WHERE task_id = ? AND status IN ({placeholders})
                """,
                (
                    status,
                    safe_message,
                    now,
                    result_json,
                    error_json,
                    input_requests_json,
                    task_id,
                    *source_statuses,
                ),
            )
            changed = cursor.rowcount == 1
        if changed and status in TERMINAL_STATUSES:
            self.prune()
        return changed

    def recover_interrupted(self) -> int:
        now = _utc_timestamp(self._clock_ms())
        error = _compact_json(
            {
                "code": -32603,
                "message": "Task execution was interrupted by server restart",
            }
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks SET
                    status = 'failed',
                    status_message = 'Interrupted by server restart',
                    updated_at = ?,
                    result_json = NULL,
                    error_json = ?,
                    input_requests_json = NULL
                WHERE status IN ('working', 'input_required')
                """,
                (now, error),
            )
            recovered = cursor.rowcount
        self.prune()
        return recovered

    def prune(self) -> int:
        now_ms = self._clock_ms()
        with self._connect() as connection:
            expired = connection.execute(
                "DELETE FROM tasks WHERE expires_at_ms IS NOT NULL AND expires_at_ms <= ?",
                (now_ms,),
            ).rowcount
            excess = connection.execute(
                """
                SELECT MAX(COUNT(*) - ?, 0)
                FROM tasks
                WHERE status IN ('completed', 'failed', 'cancelled')
                """,
                (self.max_retained,),
            ).fetchone()[0]
            removed = 0
            if excess:
                removed = connection.execute(
                    """
                    DELETE FROM tasks WHERE task_id IN (
                        SELECT task_id FROM tasks
                        WHERE status IN ('completed', 'failed', 'cancelled')
                        ORDER BY updated_at ASC, task_id ASC
                        LIMIT ?
                    )
                    """,
                    (excess,),
                ).rowcount
        return expired + removed

    @staticmethod
    def _from_row(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            owner_digest=row["owner_digest"],
            tool_name=row["tool_name"],
            required_scopes=tuple(json.loads(row["required_scopes_json"])),
            status=row["status"],
            status_message=row["status_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at_ms=row["expires_at_ms"],
            ttl_ms=row["ttl_ms"],
            poll_interval_ms=row["poll_interval_ms"],
            result=json.loads(row["result_json"]) if row["result_json"] is not None else None,
            error=json.loads(row["error_json"]) if row["error_json"] is not None else None,
            input_requests=(json.loads(row["input_requests_json"]) if row["input_requests_json"] is not None else None),
        )
