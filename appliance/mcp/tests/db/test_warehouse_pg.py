"""Real-PostgreSQL warehouse round-trip (feature 012).

Runs only when QMT_TEST_DB_URL points at a reachable PostgreSQL AND asyncpg is
installed (skipped otherwise). Exercises migrate -> upsert -> coverage -> read and
idempotent re-upsert against a live DB.

    QMT_TEST_DB_URL=postgresql://postgres:test@127.0.0.1:55432/qmt \
        python -m pytest -m db
"""

from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("asyncpg")
pytestmark = pytest.mark.db

DB_URL = os.environ.get("QMT_TEST_DB_URL", "")

from qmt_mcp_db.engine import DbEngine  # noqa: E402
from qmt_mcp_db.migrations import apply_migrations  # noqa: E402
from qmt_mcp_db.warehouse import Warehouse  # noqa: E402


@pytest.fixture
def engine():
    if not DB_URL:
        pytest.skip("set QMT_TEST_DB_URL to run the DB tier")
    eng = DbEngine(DB_URL)
    eng.connect()
    apply_migrations(eng)
    yield eng
    eng.close()


def test_warehouse_round_trip(engine):
    broker = f"test_{uuid.uuid4().hex[:8]}"  # isolate this run by broker_id namespace
    wh = Warehouse(engine, broker)
    rows = [
        {
            "code": "600000.SH",
            "time": "20250101",
            "open": 10.0,
            "high": 11.0,
            "low": 9.5,
            "close": 10.5,
            "volume": 1000,
            "amount": 10500.0,
        },
        {
            "code": "600000.SH",
            "time": "20250102",
            "open": 10.5,
            "high": 11.5,
            "low": 10.0,
            "close": 11.0,
            "volume": 1200,
            "amount": 13200.0,
        },
    ]
    assert wh.upsert_bars("600000.SH", "1d", "none", rows) == 2

    cov = wh.coverage("600000.SH", "1d", "none")
    assert cov == {"min": "20250101", "max": "20250102", "count": 2}

    read = wh.read_bars("600000.SH", "1d", "none", "20250101", "20250102")
    assert [r["time"] for r in read] == ["20250101", "20250102"]
    assert read[0]["close"] == 10.5

    # idempotent re-upsert with a changed value: count stays 2, value updated
    rows[0]["close"] = 42.0
    wh.upsert_bars("600000.SH", "1d", "none", rows)
    assert wh.coverage("600000.SH", "1d", "none")["count"] == 2
    again = wh.read_bars("600000.SH", "1d", "none", "20250101", "20250101")
    assert again[0]["close"] == 42.0

    # cleanup this run's namespace
    engine.execute("DELETE FROM md_bars WHERE broker_id = $1", broker)
