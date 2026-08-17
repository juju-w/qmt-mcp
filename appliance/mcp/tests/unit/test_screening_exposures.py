from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_screening.exposures import canonical_exposure, exposure_groups, match_exposure
from tests.screening_fixtures import load_screening_fixture


def test_csi_500_aliases_resolve_to_one_canonical_group():
    assert canonical_exposure("中证500") == "csi_500"
    assert canonical_exposure("CSI-500") == "csi_500"
    assert canonical_exposure("zz500") == "csi_500"


def test_csi_500_membership_requires_exposure_name_not_code_digits():
    records = load_screening_fixture("etf_universe.json")["records"]
    matched = [row["code"] for row in records if match_exposure(row, "csi_500")]
    assert matched == ["510500.SH", "512500.SH", "159922.SZ"]


def test_unknown_exposure_returns_valid_groups():
    with pytest.raises(McpCoreError) as exc:
        canonical_exposure("量子计算500")
    assert exc.value.error_type == "validation"
    assert "csi_500" in exc.value.details["known_exposure_groups"]


def test_exposure_groups_have_localized_labels_and_aliases():
    csi500 = next(item for item in exposure_groups("zh-CN") if item["id"] == "csi_500")
    assert csi500["label"] == "中证500"
    assert "CSI500" in csi500["aliases"]
