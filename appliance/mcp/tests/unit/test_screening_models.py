from __future__ import annotations

import ast
from pathlib import Path

from qmt_mcp_screening.models import FactorObservation, canonical_factor_ref


def test_canonical_factor_ref_applies_stable_parameter_order():
    assert canonical_factor_ref("return", {"window": 60, "unused": False}) == (
        "return",
        (("unused", False), ("window", 60)),
    )


def test_factor_observation_serializes_missing_state_without_numeric_zero():
    observation = FactorObservation.missing(
        code="600001.SH",
        factor_id="roe_ttm",
        params={},
        reason="insufficient_history",
        unit="ratio",
    )
    payload = observation.to_dict()
    assert payload["status"] == "missing"
    assert payload["value"] is None
    assert payload["missing_reason"] == "insufficient_history"


def test_pure_screening_modules_have_no_heavy_or_runtime_imports():
    package = Path(__file__).parents[2] / "qmt_mcp_screening"
    forbidden = {"xtquant", "numpy", "pandas", "mcp", "pydantic", "asyncpg"}
    runtime_boundaries = {"sources.py", "tools.py"}
    for path in package.glob("*.py"):
        if path.name in runtime_boundaries:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        assert not imports.intersection(forbidden), f"{path.name}: {imports.intersection(forbidden)}"
