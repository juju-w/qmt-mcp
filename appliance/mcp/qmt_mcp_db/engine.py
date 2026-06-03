"""asyncpg pool on a background asyncio loop, exposed via a sync facade (012).

asyncpg is native-async; the MCP tool layer is sync (registry + WorkerPool). This
runs one asyncio loop in a daemon thread and submits coroutines to it via
`run_coroutine_threadsafe`, so callers get a blocking API while DB I/O stays
async and off the request/event loop. `asyncpg` is imported lazily — this module
is only used when the DB is enabled.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from qmt_mcp_core.errors import McpCoreError


class DbEngine:
    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 5, timeout: float = 10.0):
        self.dsn = dsn
        self.min_size = max(1, min_size)
        self.max_size = max(self.min_size, max_size)
        self.timeout = timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._pool: Any = None

    def _start_loop(self) -> None:
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="qmt-db-loop", daemon=True)
        self._thread.start()

    def run(self, coro, timeout: float | None = None) -> Any:
        if self._loop is None:
            raise McpCoreError("dependency", "db engine not started")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return fut.result(timeout=timeout or self.timeout)
        except McpCoreError:
            raise
        except Exception as exc:
            raise McpCoreError("dependency", f"db call failed: {type(exc).__name__}: {exc}") from exc

    def connect(self) -> None:
        import asyncpg  # lazy: only when DB enabled

        self._start_loop()

        async def _mk():
            return await asyncpg.create_pool(dsn=self.dsn, min_size=self.min_size, max_size=self.max_size)

        self._pool = self.run(_mk(), timeout=self.timeout)

    @property
    def connected(self) -> bool:
        return self._pool is not None

    def execute(self, sql: str, *args: Any) -> Any:
        async def _x():
            async with self._pool.acquire() as con:
                return await con.execute(sql, *args)

        return self.run(_x())

    def executemany(self, sql: str, args_list: list[tuple]) -> None:
        async def _x():
            async with self._pool.acquire() as con:
                await con.executemany(sql, args_list)

        self.run(_x())

    def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        async def _x():
            async with self._pool.acquire() as con:
                rows = await con.fetch(sql, *args)
                return [dict(r) for r in rows]

        return self.run(_x())

    def close(self) -> None:
        if self._pool is not None:

            async def _c():
                await self._pool.close()

            try:
                self.run(_c(), timeout=5)
            except Exception:
                pass
            self._pool = None
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop = None
