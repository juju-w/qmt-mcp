from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_screening.cache import FactorObservationCache, ScreenResultStore
from qmt_mcp_screening.service import ScreeningService, UniverseResolver
from tests.screening_fixtures import daily_rows, load_screening_fixture


class EtfSource:
    broker_id = "fixture"
    capabilities = frozenset({"daily_bars", "snapshot", "instrument_detail"})

    def __init__(self, amounts: dict[str, float]):
        self.amounts = amounts
        self.daily_code_batches: list[list[str]] = []
        self.snapshot_codes: list[str] = []

    def daily_bars(self, codes, **_kwargs):
        self.daily_code_batches.append(list(codes))
        return {
            code: tuple(daily_rows(code, [10 + index * 0.01 for index in range(21)], amount=self.amounts[code]))
            for code in codes
        }

    def snapshots(self, codes, **_kwargs):
        self.snapshot_codes.extend(codes)
        return {code: {"bid1": 9.99, "ask1": 10.01, "time": "20260816100000", "missing_reason": None} for code in codes}

    def financial_tables(self, *_args, **_kwargs):
        raise AssertionError("ETF screen must not read financial data")

    def data_context(self, *, as_of="", captured_at=""):
        from qmt_mcp_screening.models import DataContext

        return DataContext(
            captured_at=captured_at or "2026-08-16T10:00:00+08:00",
            as_of=as_of or "20260814",
            market_session="20260814",
            price_adjustment="front_ratio",
            factor_version="screening-factors-v1",
            broker_id=self.broker_id,
        )


def test_strict_csi500_membership_precedes_liquidity_and_spread_rank():
    records = load_screening_fixture("etf_universe.json")["records"]
    cache = {"records": records}
    resolver = UniverseResolver(cache_provider=lambda: cache, sector_provider=lambda _sector: [])
    source = EtfSource(
        {
            "510500.SH": 300_000_000,
            "512500.SH": 200_000_000,
            "159922.SZ": 100_000_000,
            "513500.SH": 9_000_000_000,
            "515000.SH": 8_000_000_000,
            "516500.SH": 7_000_000_000,
        }
    )
    service = ScreeningService(resolver=resolver, source=source, result_store=ScreenResultStore())

    result = service.screen(
        {
            "asset_type": "etf",
            "etf_profile": "broad_market_equity",
            "universe": {"kind": "exposure", "values": ["中证500"]},
            "filters": [
                {
                    "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                    "operator": "gte",
                    "value": 1,
                }
            ],
            "rank": [
                {
                    "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                    "weight": 0.8,
                },
                {
                    "factor": {"factor_id": "bid_ask_spread_bps", "params": {}},
                    "weight": 0.2,
                    "direction": "lower",
                    "missing_policy": "neutral",
                },
            ],
            "limit": 5,
        }
    )

    returned = [row["code"] for row in result["results"]]
    assert returned == ["510500.SH", "512500.SH", "159922.SZ"]
    assert not {"513500.SH", "515000.SH", "516500.SH"}.intersection(returned)
    assert source.snapshot_codes == ["159922.SZ", "510500.SH", "512500.SH"]
    assert result["universe"]["exposure_group"] == "csi_500"
    assert result["stage_counts"] == {
        "resolved": 3,
        "data_eligible": 3,
        "passed_filters": 3,
        "ranked": 3,
        "returned": 3,
    }
    assert result["screen_id"].startswith("scr_")
    assert next(source for source in result["data_context"]["sources"] if source["name"] == "xtdata-daily-bars")[
        "as_of"
    ]


def test_repeated_screen_reuses_daily_factors_and_only_briefly_reuses_snapshot_factors():
    records = load_screening_fixture("etf_universe.json")["records"]
    resolver = UniverseResolver(cache_provider=lambda: {"records": records}, sector_provider=lambda _sector: [])
    source = EtfSource({code: 100_000_000 for code in ("510500.SH", "512500.SH", "159922.SZ")})
    now = [100.0]
    service = ScreeningService(
        resolver=resolver,
        source=source,
        factor_cache=FactorObservationCache(time_fn=lambda: now[0]),
    )
    request = {
        "asset_type": "etf",
        "etf_profile": "broad_market_equity",
        "universe": {"kind": "exposure", "values": ["csi_500"]},
        "rank": [
            {"factor": {"factor_id": "avg_amount", "params": {"window": 20}}, "weight": 0.8},
            {
                "factor": {"factor_id": "bid_ask_spread_bps", "params": {}},
                "weight": 0.2,
                "direction": "lower",
                "missing_policy": "neutral",
            },
        ],
    }

    first = service.screen(request)
    second = service.screen(request)
    assert first["cache"] == {"factor_hits": 0, "factor_misses": 6}
    assert second["cache"] == {"factor_hits": 6, "factor_misses": 0}
    assert len(source.daily_code_batches) == 1
    assert len(source.snapshot_codes) == 3

    now[0] += 6
    third = service.screen(request)
    assert third["cache"] == {"factor_hits": 3, "factor_misses": 3}
    assert len(source.daily_code_batches) == 1
    assert len(source.snapshot_codes) == 6


def test_auto_profile_refuses_mixed_etf_categories_and_comparison_preset_requires_exposure():
    records = [
        {"code": "510500.SH", "name": "中证500ETF", "instrument_type": "etf"},
        {"code": "511010.SH", "name": "国债ETF", "instrument_type": "etf"},
    ]
    resolver = UniverseResolver(cache_provider=lambda: {"records": records}, sector_provider=lambda _sector: [])
    service = ScreeningService(
        resolver=resolver,
        source=EtfSource({"510500.SH": 100_000_000, "511010.SH": 100_000_000}),
    )
    with pytest.raises(McpCoreError, match="multiple incomparable groups"):
        service.screen(
            {
                "asset_type": "etf",
                "universe": {"kind": "codes", "values": ["510500.SH", "511010.SH"]},
                "rank": [
                    {
                        "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                        "weight": 1,
                    }
                ],
            }
        )

    with pytest.raises(McpCoreError, match="requires one resolved exposure group"):
        service.screen(
            {
                "asset_type": "etf",
                "etf_profile": "sector_theme_equity",
                "universe": {"kind": "codes", "values": ["510500.SH"]},
                "preset_id": "etf_rotation",
            }
        )
