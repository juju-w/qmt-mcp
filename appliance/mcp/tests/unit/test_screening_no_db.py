from __future__ import annotations

import sys

from qmt_mcp_screening.cache import ScreenResultStore
from qmt_mcp_screening.service import ScreeningService, UniverseResolver
from tests.screening_fixtures import daily_rows


class NoDbSource:
    broker_id = "fixture"
    capabilities = frozenset({"daily_bars", "instrument_detail"})
    database_state = "error"

    def daily_bars(self, codes, **_kwargs):
        return {code: tuple(daily_rows(code, [10.0] * 21)) for code in codes}

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


def test_current_screen_and_explanation_need_no_postgresql_or_asyncpg(monkeypatch):
    monkeypatch.delenv("QMT_DB_URL", raising=False)
    records = [{"code": "510500.SH", "name": "中证500ETF", "instrument_type": "etf"}]
    service = ScreeningService(
        resolver=UniverseResolver(cache_provider=lambda: {"records": records}, sector_provider=lambda _sector: []),
        source=NoDbSource(),
        result_store=ScreenResultStore(),
    )
    result = service.screen(
        {
            "asset_type": "etf",
            "universe": {"kind": "codes", "values": ["510500.SH"]},
            "sort": [
                {
                    "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                    "direction": "desc",
                }
            ],
        }
    )
    assert service.explain(result["screen_id"], "510500.SH")["state"] == "selected"
    assert service.source.database_state == "error"
    assert "asyncpg" not in sys.modules
