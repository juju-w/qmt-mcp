from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_screening.service import ScreeningService, UniverseResolver
from qmt_mcp_screening.validation import normalize_screen_request
from tests.screening_fixtures import daily_rows


class CapacitySource:
    broker_id = "fixture"
    capabilities = frozenset({"daily_bars", "instrument_detail", "financial_data"})

    def __init__(self):
        self.daily_counts = []
        self.financial_codes = []

    def daily_bars(self, codes, *, count, **_kwargs):
        self.daily_counts.append(count)
        return {
            code: tuple(
                daily_rows(
                    code,
                    [10.0] * count,
                    amount=100_000_000 if int(code[:6]) % 2 == 0 else 1_000,
                )
            )
            for code in codes
        }

    def financial_tables(self, codes, _tables, **_kwargs):
        self.financial_codes.extend(codes)
        rows = {
            "Income": [
                {"report_date": "20231231", "announce_time": "20240301", "net_profit": 10},
            ],
            "Balance": [
                {"report_date": "20231231", "announce_time": "20240301", "equity": 100},
            ],
        }
        return {code: {table: tuple(values) for table, values in rows.items()} for code in codes}

    def snapshots(self, *_args, **_kwargs):
        return {}

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


def test_expensive_financial_reads_only_receive_market_filter_survivors():
    codes = [f"{index:06d}.SH" for index in range(10)]
    records = [
        {
            "code": code,
            "name": code,
            "instrument_type": "stock",
            "float_shares": 1_000_000_000,
            "total_shares": 1_000_000_000,
        }
        for code in codes
    ]
    sectors = {"银行": [], "证券": [], "保险": []}
    resolver = UniverseResolver(
        cache_provider=lambda: {"records": records},
        sector_provider=lambda sector: sectors.get(sector),
    )
    source = CapacitySource()
    service = ScreeningService(resolver=resolver, source=source)

    service.screen(
        {
            "asset_type": "stock",
            "stock_profile": "non_financial",
            "universe": {"kind": "codes", "values": codes},
            "as_of": "20260814",
            "filters": [
                {
                    "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                    "operator": "gte",
                    "value": 50_000_000,
                }
            ],
            "rank": [{"factor": {"factor_id": "roe_ttm", "params": {}}, "weight": 1}],
            "limit": 10,
        }
    )

    assert max(source.daily_counts) <= 260
    assert source.financial_codes == [code for code in codes if int(code[:6]) % 2 == 0]


def test_validation_still_caps_factor_references_and_public_results():
    base = {
        "asset_type": "etf",
        "universe": {"kind": "codes", "values": ["510500.SH"]},
        "rank": [{"factor": {"factor_id": "avg_amount", "params": {"window": 20}}, "weight": 1}],
    }
    with pytest.raises(McpCoreError, match="factor reference limit"):
        normalize_screen_request(
            {
                **base,
                "filters": [
                    {
                        "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                        "operator": "gte",
                        "value": 1,
                    }
                    for _ in range(24)
                ],
            }
        )
    with pytest.raises(McpCoreError, match="limit out of bounds"):
        normalize_screen_request({**base, "limit": 101})
