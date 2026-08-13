from __future__ import annotations

from qmt_mcp_apps.kline_data import build_kline_payload, kline_text, normalize_kline_rows


def test_normalize_kline_rows_filters_sorts_and_deduplicates():
    rows = [
        {"time": "2026-08-14", "open": 3, "high": 4, "low": 2, "close": 3.5, "volume": -1},
        {"time": "20260813", "open": "2", "high": "3", "low": "1", "close": "2.5"},
        {"time": "20260814", "open": 4, "high": 5, "low": 3, "close": 4.5},
        {"time": "bad", "open": 0, "high": 0, "low": 0, "close": 0},
        {"time": "20260815", "open": 4, "high": 3, "low": 2, "close": 2.5},
    ]

    result = normalize_kline_rows(rows)

    assert [row["time"] for row in result] == ["20260813", "20260814"]
    assert result[-1]["close"] == 4.5


def test_build_kline_payload_computes_summary_and_text_fallback():
    payload = build_kline_payload(
        code="688234.SH",
        name="天岳先进",
        period="1d",
        dividend_type="front",
        source="get_market_data_ex",
        rows=[
            {"time": "20260813", "open": 130, "high": 136, "low": 129, "close": 135, "volume": 100},
            {"time": "20260814", "open": 134.8, "high": 136.8, "low": 133.9, "close": 136.42, "volume": 120},
        ],
    )

    assert payload["range"] == {"start": "20260813", "end": "20260814", "bar_count": 2}
    assert round(payload["summary"]["change"], 2) == 1.42
    assert payload["summary"]["high"] == 136.8
    text = kline_text(payload)
    assert "天岳先进 (688234.SH)" in text
    assert "2 bars" in text
    assert "latest close +136.42" in text


def test_empty_payload_and_error_text_remain_meaningful():
    payload = build_kline_payload(
        code="688234.SH",
        name="天岳先进",
        period="1d",
        dividend_type="front",
        source="get_market_data_ex",
        rows=[],
    )

    assert payload["bars"] == []
    assert payload["summary"]["latest_close"] is None
    assert "0 bars" in kline_text(payload)
    assert "not_ready" in kline_text({"ok": False, "error_type": "not_ready", "error": "QMT offline"})
