from __future__ import annotations

import pytest

from qmt_mcp_screening.financial_factors import FinancialTimeline, TimelineError
from tests.screening_fixtures import load_screening_fixture


def test_announcement_cutoff_and_ytd_ttm_assembly_prevent_future_leakage():
    fixture = load_screening_fixture("financial_timeline.json")
    timeline = FinancialTimeline(fixture, as_of="20241101")

    assert timeline.latest("Income")["report_date"] == "20240930"
    assert timeline.ttm("Income", "revenue") == pytest.approx(140.0)
    assert timeline.ttm("Income", "net_profit") == pytest.approx(19.0)
    assert timeline.ttm("CashFlow", "operating_cash_flow") == pytest.approx(22.0)
    assert timeline.latest("Balance")["total_assets"] == 240
    assert all(row["announce_time"] <= "20241101" for row in timeline.rows("Income"))


def test_annual_report_is_ttm_and_latest_restatement_wins():
    rows = {
        "Income": [
            {"report_date": "20231231", "announce_time": "20240301", "revenue": 100},
            {"report_date": "20231231", "announce_time": "20240401", "revenue": 105},
        ]
    }
    timeline = FinancialTimeline(rows, as_of="20240501")
    assert timeline.ttm("Income", "revenue") == pytest.approx(105.0)
    assert timeline.latest("Income")["announce_time"] == "20240401"


def test_irreconcilable_duplicate_and_malformed_rows_are_rejected():
    duplicate = {
        "Income": [
            {"report_date": "20231231", "announce_time": "20240301", "revenue": 100},
            {"report_date": "20231231", "announce_time": "20240301", "revenue": 101},
        ]
    }
    with pytest.raises(TimelineError, match="conflicting duplicate"):
        FinancialTimeline(duplicate, as_of="20240501")

    malformed = {"Income": [{"report_date": "not-a-date", "announce_time": "20240301"}]}
    with pytest.raises(TimelineError, match="malformed"):
        FinancialTimeline(malformed, as_of="20240501")
