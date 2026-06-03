"""Unit tests for warehouse coverage math (feature 012)."""

from __future__ import annotations

from qmt_mcp_db.coverage import is_covered


def test_covered_when_within_cached_range():
    assert is_covered("20250101", "20250131", "20250105", "20250120") is True
    assert is_covered("20250101", "20250131", "20250101", "20250131") is True


def test_not_covered_when_outside():
    assert is_covered("20250105", "20250120", "20250101", "20250120") is False  # start before cache
    assert is_covered("20250105", "20250120", "20250105", "20250131") is False  # end after cache


def test_not_covered_when_cache_empty():
    assert is_covered(None, None, "20250101", "20250131") is False


def test_open_ended_requests_fall_back():
    assert is_covered("20250101", "20250131", "", "20250120") is False
    assert is_covered("20250101", "20250131", "20250105", "") is False
