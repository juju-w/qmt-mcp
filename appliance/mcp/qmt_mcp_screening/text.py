"""Concise Chinese and English text renderers for screening tools."""

from __future__ import annotations

from typing import Any


def _error(payload: dict[str, Any]) -> str:
    return f"{payload.get('error_type', 'error')}: {payload.get('error', 'request failed')}"


def render_catalog(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return _error(payload)
    locale = payload.get("locale", "zh-CN")
    available = payload.get("availability_counts", {}).get("available", 0)
    total = len(payload.get("factors", []))
    if locale == "zh-CN":
        return (
            f"{payload['asset_type']} 因子目录 {payload['catalog_version']}：{available}/{total} 个当前可用。"
            f"请按返回的 factor_id、参数、单位和 profile 构造 qmt_screen_instruments；不要猜测未列出的名称。"
        )
    return (
        f"{payload['asset_type']} factor catalog {payload['catalog_version']}: {available}/{total} currently available. "
        "Build qmt_screen_instruments from the returned IDs, parameters, units, and profile; do not guess names."
    )


def _score(value: Any) -> str:
    return "--" if value is None else f"{float(value):.2f}"


def render_screen(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return _error(payload)
    locale = payload.get("normalized_request", {}).get("locale", "zh-CN")
    counts = payload.get("stage_counts", {})
    rows = payload.get("results", [])[:10]
    if locale == "en":
        lines = [
            f"Screen {payload.get('screen_id')}: resolved {counts.get('resolved', 0)}, "
            f"passed {counts.get('passed_filters', 0)}, returned {counts.get('returned', 0)}."
        ]
    else:
        lines = [
            f"筛选 {payload.get('screen_id')}：解析 {counts.get('resolved', 0)}，"
            f"通过 {counts.get('passed_filters', 0)}，返回 {counts.get('returned', 0)}。"
        ]
    for row in rows:
        factors = ", ".join(
            f"{item['factor']['factor_id']}={item.get('value')}" for item in row.get("key_factors", [])[:2]
        )
        lines.append(
            f"{row.get('rank')}. {row.get('code')} {row.get('name')} score={_score(row.get('score'))} {factors}".rstrip()
        )
    if locale == "en":
        lines.append("Use qmt_explain_screen_result with this screen_id and an exact code for the captured trace.")
    else:
        lines.append("使用该 screen_id 和准确代码调用 qmt_explain_screen_result 查看本次快照的完整依据。")
    return "\n".join(lines)


def render_explanation(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return _error(payload)
    contributions = sorted(
        payload.get("rank_contributions", []),
        key=lambda item: item.get("contribution", 0),
        reverse=True,
    )
    largest = contributions[0] if contributions else None
    summary = (
        f"{payload.get('code')} {payload.get('name', '')}: {payload.get('state')}, "
        f"rank={payload.get('rank')}, score={_score(payload.get('score'))}, coverage={payload.get('coverage')}."
    )
    if largest:
        summary += (
            f" Largest contribution: {largest['factor']['factor_id']} {float(largest.get('contribution', 0)):.2f}."
        )
    return summary
