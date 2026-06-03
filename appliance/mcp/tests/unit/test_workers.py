"""Unit tests for the bounded worker pool (sync path)."""

from __future__ import annotations

import time

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_core.workers import WorkerPool


def test_run_sync_returns_value():
    pool = WorkerPool(2)
    assert pool.run_sync(lambda x: x * 2, 21) == 42


def test_run_sync_timeout_maps_to_dependency():
    pool = WorkerPool(2)

    def slow():
        time.sleep(0.5)
        return "late"

    with pytest.raises(McpCoreError) as exc:
        pool.run_sync(slow, timeout=0.01)
    assert exc.value.error_type == "dependency"


def test_run_sync_capacity_exhausted():
    pool = WorkerPool(1)
    # Saturate the bounded sync semaphore to simulate no free capacity.
    assert pool._sync_sem.acquire(blocking=False) is True
    try:
        with pytest.raises(McpCoreError) as exc:
            pool.run_sync(lambda: "x")
        assert exc.value.error_type == "capacity"
    finally:
        pool._sync_sem.release()
