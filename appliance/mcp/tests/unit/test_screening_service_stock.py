from __future__ import annotations

import pytest

from qmt_mcp_screening.service import ScreeningService, UniverseResolver
from tests.screening_fixtures import daily_rows, load_screening_fixture


class StockSource:
    broker_id = "fixture"
    capabilities = frozenset({"daily_bars", "instrument_detail", "financial_data"})

    def __init__(self, financial):
        self.financial = financial
        self.financial_codes: list[str] = []

    def daily_bars(self, codes, *, dividend_type="front_ratio", **_kwargs):
        amount = 100_000_000
        return {
            code: tuple(daily_rows(code, [10 + index * 0.1 for index in range(61)], amount=amount)) for code in codes
        }

    def snapshots(self, *_args, **_kwargs):
        raise AssertionError("snapshot is not requested")

    def financial_tables(self, codes, _tables, **_kwargs):
        self.financial_codes.extend(codes)
        return {code: {table: tuple(rows) for table, rows in self.financial.items()} for code in codes}

    def data_context(self, *, as_of="", captured_at=""):
        from qmt_mcp_screening.models import DataContext

        return DataContext(
            captured_at=captured_at or "2024-11-01T10:00:00+08:00",
            as_of=as_of,
            market_session="20241031",
            price_adjustment="front_ratio",
            factor_version="screening-factors-v1",
            broker_id=self.broker_id,
        )


def test_nonfinancial_profile_and_announcement_cutoff_are_enforced_before_rank():
    fixture = load_screening_fixture("stock_profiles.json")
    records = []
    for record in fixture["records"]:
        records.append({**record, "float_shares": 8_000_000_000, "total_shares": 9_000_000_000})
    sectors = fixture["sector_members"]
    resolver = UniverseResolver(
        cache_provider=lambda: {"records": records},
        sector_provider=lambda sector: sectors.get(sector),
    )
    source = StockSource(load_screening_fixture("financial_timeline.json"))
    service = ScreeningService(resolver=resolver, source=source)

    result = service.screen(
        {
            "asset_type": "stock",
            "stock_profile": "non_financial",
            "universe": {"kind": "sector", "values": ["沪深A股"]},
            "as_of": "20241101",
            "filters": [
                {
                    "factor": {"factor_id": "avg_amount", "params": {"window": 60}},
                    "operator": "gte",
                    "value": 50_000_000,
                },
                {
                    "factor": {"factor_id": "earnings_yield_ttm", "params": {}},
                    "operator": "gt",
                    "value": 0,
                },
            ],
            "rank": [
                {"factor": {"factor_id": "earnings_yield_ttm", "params": {}}, "weight": 0.5},
                {"factor": {"factor_id": "roe_ttm", "params": {}}, "weight": 0.5},
            ],
            "limit": 10,
        }
    )

    assert source.financial_codes == ["600001.SH"]
    assert [row["code"] for row in result["results"]] == ["600001.SH"]
    assert result["results"][0]["profile"] == "non_financial"
    assert result["stage_counts"]["resolved"] == 4
    assert result["stage_counts"]["data_eligible"] == 1
    assert result["data_context"]["as_of"] == "20241101"
    sources = {source["name"]: source["as_of"] for source in result["data_context"]["sources"]}
    assert sources["xtdata-daily-bars"]
    assert sources["xtdata-announced-financial"] == "20241028"
    assert result["results"][0]["score"] == pytest.approx(
        sum(item["contribution"] for item in result["results"][0]["key_factors"])
    )
    explanation = service.explain(result["screen_id"], "600001.SH")
    earnings = explanation["factors"]["earnings_yield_ttm"]
    assert earnings["value"] == pytest.approx(19 / (16 * 1_200_000_000))
    assert earnings["announcement_time"] == "20241028"

    historical_cap = service.screen(
        {
            "asset_type": "stock",
            "stock_profile": "non_financial",
            "universe": {"kind": "sector", "values": ["沪深A股"]},
            "as_of": "20241101",
            "sort": [{"factor": {"factor_id": "total_market_cap", "params": {}}, "direction": "desc"}],
        }
    )
    cap_explanation = service.explain(historical_cap["screen_id"], "600001.SH")
    capital = cap_explanation["factors"]["total_market_cap"]
    assert capital["value"] == pytest.approx(16 * 1_200_000_000)
    assert capital["announcement_time"] == "20241028"
    assert next(record for record in records if record["code"] == "600001.SH")["total_shares"] == 9_000_000_000
