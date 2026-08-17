from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_screening.service import ScreeningService, UniverseResolver
from tests.screening_fixtures import daily_rows


class MarketOnlySource:
    broker_id = "fixture"
    capabilities = frozenset({"daily_bars", "instrument_detail"})

    def __init__(self):
        self.daily_calls = 0

    def daily_bars(self, codes, **_kwargs):
        self.daily_calls += 1
        return {code: tuple(daily_rows(code, [10.0] * 21, amount=100_000_000)) for code in codes}

    def data_context(self, *, as_of="", captured_at=""):
        from qmt_mcp_screening.models import DataContext

        return DataContext(
            captured_at=captured_at,
            as_of=as_of or "20260814",
            market_session="20260814",
            price_adjustment="front_ratio",
            factor_version="screening-factors-v1",
            broker_id=self.broker_id,
        )


def service():
    records = [
        {
            "code": "600001.SH",
            "name": "示例制造",
            "instrument_type": "stock",
            "total_shares": 1_000_000_000,
        }
    ]
    sectors = {"银行": [], "证券": [], "保险": []}
    return ScreeningService(
        resolver=UniverseResolver(
            cache_provider=lambda: {"records": records}, sector_provider=lambda sector: sectors.get(sector)
        ),
        source=MarketOnlySource(),
    )


def base_request(missing_policy: str):
    return {
        "asset_type": "stock",
        "stock_profile": "non_financial",
        "universe": {"kind": "codes", "values": ["600001.SH"]},
        "rank": [
            {
                "factor": {"factor_id": "roe_ttm", "params": {}},
                "weight": 1,
                "missing_policy": missing_policy,
            }
        ],
    }


def test_unavailable_hard_filter_fails_before_scanning():
    instance = service()
    with pytest.raises(McpCoreError) as error:
        instance.screen(
            {
                **base_request("neutral"),
                "filters": [
                    {
                        "factor": {"factor_id": "roe_ttm", "params": {}},
                        "operator": "gt",
                        "value": 0,
                    }
                ],
            }
        )
    assert error.value.error_type == "capability"
    assert "financial_data" in error.value.details["missing_capabilities"]
    assert error.value.details["repair_tools"] == ["qmt_xtdata_download_financial_data"]
    assert instance.source.daily_calls == 0


def test_optional_neutral_retains_candidate_with_half_score_and_zero_coverage():
    instance = service()
    result = instance.screen(base_request("neutral"))
    row = result["results"][0]
    assert row["score"] == pytest.approx(50)
    assert row["coverage"] == 0
    assert row["key_factors"][0]["missing_reason"] == "unavailable_capability"
    assert result["coverage"]["overall"] == 0
    explanation = instance.explain(result["screen_id"], "600001.SH")
    assert explanation["rank_contributions"][0]["missing_policy"] == "neutral"
    assert explanation["rank_contributions"][0]["effective_weight"] == 1
    assert explanation["eligible"] is True


def test_optional_exclude_removes_candidate_and_fail_rejects_request():
    assert service().screen(base_request("exclude"))["results"] == []
    with pytest.raises(McpCoreError) as error:
        service().screen(base_request("fail"))
    assert error.value.error_type == "capability"


class PartialSource(MarketOnlySource):
    def __init__(self):
        super().__init__()
        self.errors = []

    def daily_bars(self, codes, **_kwargs):
        self.daily_calls += 1
        self.errors.append({"source": "daily_bars", "codes": ["600002.SH"], "error_type": "RuntimeError"})
        return {
            code: (
                ({"code": code, "time": "", "_source_error": "RuntimeError"},)
                if code == "600002.SH"
                else tuple(daily_rows(code, [10.0] * 21, amount=100_000_000))
            )
            for code in codes
        }


def test_one_candidate_source_error_is_isolated_and_penalizes_coverage():
    records = [
        {"code": "600001.SH", "name": "正常制造", "instrument_type": "stock"},
        {"code": "600002.SH", "name": "缺失制造", "instrument_type": "stock"},
    ]
    sectors = {"银行": [], "证券": [], "保险": []}
    instance = ScreeningService(
        resolver=UniverseResolver(
            cache_provider=lambda: {"records": records}, sector_provider=lambda sector: sectors.get(sector)
        ),
        source=PartialSource(),
    )
    result = instance.screen(
        {
            "asset_type": "stock",
            "stock_profile": "non_financial",
            "universe": {"kind": "codes", "values": ["600001.SH", "600002.SH"]},
            "rank": [
                {
                    "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                    "weight": 1,
                    "missing_policy": "neutral",
                }
            ],
        }
    )
    by_code = {row["code"]: row for row in result["results"]}
    assert by_code["600001.SH"]["coverage"] == 1
    assert by_code["600002.SH"]["coverage"] == 0
    assert by_code["600002.SH"]["key_factors"][0]["missing_reason"] == "source_error"
    assert any("source batch error" in warning for warning in result["warnings"])


class HistoricalEtfSource(MarketOnlySource):
    capabilities = frozenset({"daily_bars", "instrument_detail", "snapshot", "etf_iopv"})

    def __init__(self):
        super().__init__()
        self.snapshot_calls = 0

    def snapshots(self, *_args, **_kwargs):
        self.snapshot_calls += 1
        raise AssertionError("historical screens must not substitute today's snapshot")


def test_historical_screen_never_substitutes_current_snapshot_and_iopv_stays_gated():
    records = [{"code": "510500.SH", "name": "中证500ETF", "instrument_type": "etf"}]
    source = HistoricalEtfSource()
    instance = ScreeningService(
        resolver=UniverseResolver(cache_provider=lambda: {"records": records}, sector_provider=lambda _sector: []),
        source=source,
    )
    result = instance.screen(
        {
            "asset_type": "etf",
            "universe": {"kind": "codes", "values": ["510500.SH"]},
            "as_of": "20260814",
            "rank": [
                {"factor": {"factor_id": "avg_amount", "params": {"window": 20}}, "weight": 0.5},
                {
                    "factor": {"factor_id": "bid_ask_spread_bps", "params": {}},
                    "weight": 0.5,
                    "missing_policy": "neutral",
                },
            ],
        }
    )
    assert source.snapshot_calls == 0
    assert result["results"][0]["coverage"] == 0.5
    assert any("historical_snapshot" in warning for warning in result["warnings"])

    with pytest.raises(McpCoreError) as error:
        instance.screen(
            {
                "asset_type": "etf",
                "universe": {"kind": "codes", "values": ["510500.SH"]},
                "rank": [
                    {
                        "factor": {"factor_id": "premium_to_iopv", "params": {}},
                        "weight": 1,
                        "missing_policy": "fail",
                    }
                ],
            }
        )
    assert error.value.error_type == "capability"
    assert "screening_implementation" in error.value.details["missing_capabilities"]
