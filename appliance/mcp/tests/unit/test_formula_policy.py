from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_xtdata.formula_policy import FormulaPolicy


def test_formula_policy_allowlist_and_sandbox(tmp_path):
    policy = FormulaPolicy("VIX_HELPER", str(tmp_path))
    assert policy.require_formula("VIX_HELPER") == "VIX_HELPER"
    assert policy.require_output_path("out.feather").startswith(str(tmp_path))
    with pytest.raises(McpCoreError):
        policy.require_formula("OTHER")
    with pytest.raises(McpCoreError):
        policy.require_output_path("/tmp/out.feather")
