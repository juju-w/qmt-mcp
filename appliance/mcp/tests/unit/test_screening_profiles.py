from __future__ import annotations

from qmt_mcp_screening.profiles import classify_stock_profiles
from tests.screening_fixtures import load_screening_fixture


def test_financial_profiles_are_classified_from_complete_exact_sector_sets():
    fixture = load_screening_fixture("stock_profiles.json")
    result = classify_stock_profiles(
        [row["code"] for row in fixture["records"]],
        fixture["sector_members"],
    )
    assert result["profiles"] == {
        "600001.SH": "non_financial",
        "600002.SH": "bank",
        "600003.SH": "broker",
        "600004.SH": "insurer",
    }
    assert result["complete"] is True


def test_non_financial_residual_is_unknown_when_a_classifier_set_is_missing():
    fixture = load_screening_fixture("stock_profiles.json")
    sectors = dict(fixture["sector_members"])
    sectors.pop("保险")
    result = classify_stock_profiles(["600001.SH", "600002.SH"], sectors)
    assert result["profiles"]["600002.SH"] == "bank"
    assert result["profiles"]["600001.SH"] == "unknown"
    assert result["complete"] is False
    assert "保险" in result["missing_sectors"]
