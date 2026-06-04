"""Serializers for optional xtdata reference-data APIs."""

from __future__ import annotations

from typing import Any

from .serializers import json_clean


def rows_from_any(raw: Any, *, limit: int = 5000) -> tuple[list[dict[str, Any]], bool]:
    clean = json_clean(raw)
    if clean is None:
        return [], False
    if isinstance(clean, list):
        rows = [item if isinstance(item, dict) else {"value": item} for item in clean]
    elif isinstance(clean, dict):
        if all(isinstance(value, dict) for value in clean.values()):
            rows = [{"key": key, **value} for key, value in clean.items()]
        else:
            rows = [clean]
    else:
        rows = [{"value": clean}]
    return rows[:limit], len(rows) > limit


def financial_groups(raw: Any, *, limit: int = 5000) -> tuple[list[dict[str, Any]], bool]:
    clean = json_clean(raw) or {}
    groups: list[dict[str, Any]] = []
    truncated = False
    if not isinstance(clean, dict):
        rows, truncated = rows_from_any(clean, limit=limit)
        return [{"code": "", "table": "", "rows": rows}], truncated
    for code, by_table in clean.items():
        if not isinstance(by_table, dict):
            rows, was_truncated = rows_from_any(by_table, limit=limit)
            truncated = truncated or was_truncated
            groups.append({"code": str(code), "table": "", "rows": rows})
            continue
        for table, payload in by_table.items():
            rows, was_truncated = rows_from_any(payload, limit=limit)
            truncated = truncated or was_truncated
            groups.append({"code": str(code), "table": str(table), "rows": rows})
    return groups, truncated


def download_status(raw: Any) -> dict[str, Any]:
    return {"completed": bool(raw) if raw is not None else True, "raw_result": json_clean(raw)}
