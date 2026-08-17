from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_screening.service import UniverseResolver
from tests.screening_fixtures import load_screening_fixture


def _resolver(*, partial: bool = False):
    etf = load_screening_fixture("etf_universe.json")
    stock = load_screening_fixture("stock_profiles.json")
    records = [*etf["records"], *stock["records"]]
    sectors = stock["sector_members"] | {"沪深ETF": [row["code"] for row in etf["records"]]}
    return UniverseResolver(
        cache_provider=lambda: {"records": records, "partial": partial, "uses_seed": False},
        sector_provider=lambda name: sectors.get(name),
        max_codes=5000,
    )


def test_explicit_codes_are_deduplicated_and_asset_filtered():
    result = _resolver().resolve(
        asset_type="etf",
        universe={"kind": "codes", "values": ["510500.SH", "510500.SH", "600001.SH"]},
    )
    assert result["codes"] == ["510500.SH"]
    assert result["complete"] is True


def test_exact_sector_and_market_universes_use_membership_sources():
    sector = _resolver().resolve(
        asset_type="stock",
        universe={"kind": "sector", "values": ["沪深A股"]},
    )
    market = _resolver().resolve(
        asset_type="etf",
        universe={"kind": "market", "values": ["all_etf"]},
    )
    assert len(sector["codes"]) == 4
    assert len(market["codes"]) == 6
    assert sector["provenance"][0]["source"] == "xtdata-sector"


def test_exposure_resolves_membership_before_rank():
    result = _resolver().resolve(
        asset_type="etf",
        universe={"kind": "exposure", "values": ["csi_500"]},
    )
    assert result["codes"] == ["159922.SZ", "510500.SH", "512500.SH"]
    assert result["exposure_group"] == "csi_500"
    assert result["membership_digest"].startswith("sha256:")


def test_partial_cache_fails_closed_for_complete_exposure_claim():
    with pytest.raises(McpCoreError) as exc:
        _resolver(partial=True).resolve(
            asset_type="etf",
            universe={"kind": "exposure", "values": ["csi_500"], "policy": "require_complete"},
        )
    assert exc.value.error_type == "not_ready"


def test_partial_cache_can_be_allowed_with_warning():
    result = _resolver(partial=True).resolve(
        asset_type="etf",
        universe={"kind": "exposure", "values": ["csi_500"], "policy": "allow_partial"},
    )
    assert result["complete"] is False
    assert result["warnings"]


def test_universe_capacity_is_enforced():
    resolver = UniverseResolver(
        cache_provider=lambda: {
            "records": [
                {"code": f"{index:06d}.SH", "name": str(index), "instrument_type": "stock"} for index in range(3)
            ],
            "partial": False,
        },
        sector_provider=lambda _name: [f"{index:06d}.SH" for index in range(3)],
        max_codes=2,
    )
    with pytest.raises(McpCoreError) as exc:
        resolver.resolve(asset_type="stock", universe={"kind": "sector", "values": ["沪深A股"]})
    assert exc.value.error_type == "capacity"
