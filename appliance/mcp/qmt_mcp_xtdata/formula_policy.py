"""Formula runtime allowlist and sandbox policy."""

from __future__ import annotations

from pathlib import Path

from qmt_mcp_core.errors import McpCoreError


class FormulaPolicy:
    def __init__(self, allowlist_raw: str, sandbox: str):
        self.allowed = {item.strip() for item in (allowlist_raw or "").split(",") if item.strip()}
        self.sandbox = Path(sandbox).resolve()

    def require_formula(self, name: str) -> str:
        formula = (name or "").strip()
        if not formula:
            raise McpCoreError("validation", "formula_name must not be empty")
        if formula not in self.allowed:
            raise McpCoreError("validation", "formula is not on the server allowlist", {"formula_name": formula})
        return formula

    def require_output_path(self, value: str) -> str:
        raw = Path(value or self.sandbox / "factor.feather")
        path = raw if raw.is_absolute() else self.sandbox / raw
        resolved = path.resolve()
        if self.sandbox not in [resolved, *resolved.parents]:
            raise McpCoreError("validation", "result_path is outside formula output sandbox")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return str(resolved)
