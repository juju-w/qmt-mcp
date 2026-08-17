from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_screening.cache import ScreenResultStore
from qmt_mcp_screening.models import DataContext
from qmt_mcp_screening.service import ScreeningService, UniverseResolver
from tests.screening_fixtures import daily_rows, load_screening_fixture


class ExplainSource:
    broker_id = "fixture"
    capabilities = frozenset({"daily_bars", "instrument_detail"})

    def __init__(self):
        self.calls = 0
        self.amounts = {"510500.SH": 300_000_000, "512500.SH": 200_000_000, "159922.SZ": 100_000_000}

    def daily_bars(self, codes, **_kwargs):
        self.calls += 1
        return {code: tuple(daily_rows(code, [10.0] * 21, amount=self.amounts[code])) for code in codes}

    def data_context(self, *, as_of="", captured_at=""):
        return DataContext(
            captured_at=captured_at,
            as_of=as_of or "20260814",
            market_session="20260814",
            price_adjustment="front_ratio",
            factor_version="screening-factors-v1",
            broker_id=self.broker_id,
        )


def make_service(*, time_fn=lambda: 100.0):
    records = load_screening_fixture("etf_universe.json")["records"]
    resolver = UniverseResolver(
        cache_provider=lambda: {"records": records},
        sector_provider=lambda _sector: [],
    )
    source = ExplainSource()
    store = ScreenResultStore(ttl_seconds=10, time_fn=time_fn)
    return ScreeningService(resolver=resolver, source=source, result_store=store), source


def request():
    return {
        "asset_type": "etf",
        "etf_profile": "broad_market_equity",
        "universe": {"kind": "exposure", "values": ["csi_500"]},
        "filters": [
            {
                "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                "operator": "gte",
                "value": 150_000_000,
            }
        ],
        "rank": [
            {
                "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                "weight": 1,
            }
        ],
        "limit": 1,
    }


def test_explain_selected_unselected_and_rejected_candidates_without_source_calls():
    service, source = make_service()
    result = service.screen(request())
    calls_after_screen = source.calls

    selected = service.explain(result["screen_id"], "510500.SH")
    unselected = service.explain(result["screen_id"], "512500.SH")
    rejected = service.explain(result["screen_id"], "159922.SZ")

    assert selected["state"] == "selected"
    assert selected["rank"] == 1
    assert selected["rank_contributions"]
    assert unselected["state"] == "eligible_unselected"
    assert rejected["state"] == "rejected"
    assert rejected["filter_decisions"][0]["passed"] is False
    assert source.calls == calls_after_screen


def test_explain_rejects_unknown_code_unknown_id_and_expired_id():
    now = [100.0]
    service, _source = make_service(time_fn=lambda: now[0])
    result = service.screen(request())

    with pytest.raises(McpCoreError, match="code is not part"):
        service.explain(result["screen_id"], "513500.SH")
    with pytest.raises(McpCoreError, match="unknown or expired"):
        service.explain("scr_missing", "510500.SH")
    now[0] = 111.0
    with pytest.raises(McpCoreError, match="unknown or expired") as error:
        service.explain(result["screen_id"], "510500.SH")
    assert "rerun" in error.value.details["guidance"]
