from __future__ import annotations

from qmt_mcp_screening.tools import CATALOG_DESCRIPTION, EXPLAIN_DESCRIPTION, SCREEN_DESCRIPTION


def test_catalog_description_teaches_agents_to_discover_not_guess():
    lowered = CATALOG_DESCRIPTION.lower()
    for phrase in (
        "factor",
        "profile",
        "decimal",
        "point-in-time",
        "freshness",
        "availability",
        "do not guess",
        "does not scan",
        "qmt_screen_instruments",
    ):
        assert phrase in lowered


def test_screen_description_explains_search_profile_exposure_and_freshness_boundaries():
    lowered = SCREEN_DESCRIPTION.lower()
    for phrase in (
        "qmt_factor_catalog",
        "fuzzy relevance",
        "stocks and etfs",
        "banks/brokers/insurers",
        "exposure",
        "0.10 for 10 percent",
        "announcement-time",
        "fresh",
        "missing data",
        "mcp tasks",
    ):
        assert phrase in lowered


def test_explain_description_promises_captured_source_free_semantics():
    lowered = EXPLAIN_DESCRIPTION.lower()
    for phrase in (
        "captured",
        "does not fetch",
        "screen_id",
        "contributions",
        "missing/stale",
        "outside that screen",
        "rerun",
        "qmt_xtdata_snapshot",
    ):
        assert phrase in lowered
