"""Deterministic fixture helpers for feature 033 tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "screening"


def load_screening_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def daily_rows(code: str, closes: list[float], *, amount: float = 100_000_000.0) -> list[dict]:
    first_session = datetime(2024, 1, 2)
    return [
        {
            "code": code,
            "time": (first_session + timedelta(days=index)).strftime("%Y%m%d"),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1_000_000.0,
            "amount": amount,
            "suspendFlag": 0,
        }
        for index, close in enumerate(closes)
    ]
