"""Bounded worker executor for blocking SDK calls."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import TimeoutError
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable

from .errors import McpCoreError


class WorkerPool:
    def __init__(self, max_workers: int):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="qmt-mcp")
        self._sync_sem = threading.BoundedSemaphore(max_workers)
        self._sem = asyncio.Semaphore(max_workers)

    async def run(self, func: Callable[..., Any], *args: Any, timeout: float | None = None, **kwargs: Any) -> Any:
        if self._sem.locked() and self._sem._value <= 0:  # noqa: SLF001 - capacity smoke path
            raise McpCoreError("capacity", "worker capacity exhausted", {"max_workers": self.max_workers})
        async with self._sem:
            loop = asyncio.get_running_loop()
            call = partial(func, *args, **kwargs)
            fut = loop.run_in_executor(self._executor, call)
            if timeout:
                return await asyncio.wait_for(fut, timeout=timeout)
            return await fut

    def run_sync(
        self,
        func: Callable[..., Any],
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        acquired = self._sync_sem.acquire(blocking=False)
        if not acquired:
            raise McpCoreError("capacity", "worker capacity exhausted", {"max_workers": self.max_workers})
        try:
            future = self._executor.submit(func, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except TimeoutError as exc:
                raise McpCoreError("dependency", "worker-backed call timed out") from exc
        finally:
            self._sync_sem.release()
