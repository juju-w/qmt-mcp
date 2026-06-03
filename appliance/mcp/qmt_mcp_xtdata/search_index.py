"""Cache-backed fuzzy instrument search and ranking."""

from __future__ import annotations

import math
import re
from typing import Any

from qmt_mcp_core.errors import McpCoreError

RANK_MODES = {"combined", "relevance", "liquidity", "size", "amount", "volume"}
REFRESH_MODES = {"never", "stale", "force"}
TYPE_ORDER = {"etf": 10, "stock": 7, "index": 6, "fund": 5, "bond": 4, "future": 3, "unknown": 0}
EXTERNAL_MARKETS = {"HK", "US"}
VARIANT_TERMS = ("增强", "成长", "价值", "红利", "质量", "低波", "等权", "策略", "联接")


def norm_ascii(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "", str(value or "")).upper()


def norm_text(value: Any) -> str:
    return re.sub(r"[\s\-_./（）()【】\[\]{}]+", "", str(value or "")).upper()


def _is_code_like_query(query: str, q_ascii: str) -> bool:
    """Return true when ASCII code matching should be allowed."""
    q_text = norm_text(query)
    if not q_ascii or q_text != q_ascii:
        return False
    return bool(re.fullmatch(r"[0-9A-Z.]+", q_ascii))


def _apply_variant_penalty(
    score: float, reasons: list[str], candidate_text: str, query_text: str
) -> tuple[float, list[str]]:
    hit_terms = [term for term in VARIANT_TERMS if term in candidate_text and term not in query_text]
    if not hit_terms:
        return score, reasons
    return max(1.0, score - 32.0), reasons + [f"variant_penalty:{'/'.join(hit_terms[:3])}"]


def validate_query(query: str, limit: int, refresh: str, rank_by: str) -> str:
    clean = str(query or "").strip()
    if not clean:
        raise McpCoreError("validation", "query must not be empty")
    if len(clean) > 64:
        raise McpCoreError("validation", "query too long", {"max": 64})
    if limit < 1 or limit > 100:
        raise McpCoreError("validation", "limit out of bounds", {"min": 1, "max": 100})
    if refresh not in REFRESH_MODES:
        raise McpCoreError("validation", "invalid refresh mode", {"allowed": sorted(REFRESH_MODES)})
    if rank_by not in RANK_MODES:
        raise McpCoreError("validation", "invalid rank_by", {"allowed": sorted(RANK_MODES)})
    return clean


def validate_filters(values: list[str] | None, name: str, max_items: int = 20) -> list[str]:
    if not values:
        return []
    if len(values) > max_items:
        raise McpCoreError("validation", f"too many {name}", {"max": max_items})
    result = []
    for value in values:
        clean = str(value or "").strip()
        if clean:
            result.append(clean)
    return result


def _num(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _metric_score(record: dict[str, Any], mode: str) -> tuple[float, list[str]]:
    liquidity = record.get("liquidity") if isinstance(record.get("liquidity"), dict) else {}
    size = record.get("size") if isinstance(record.get("size"), dict) else {}
    amount = max(
        _num(liquidity.get("avg_amount_20d")),
        _num(liquidity.get("avg_amount_5d")),
        _num(liquidity.get("latest_amount")),
    )
    volume = max(_num(liquidity.get("avg_volume_20d")), _num(liquidity.get("latest_volume")))
    market_value = max(_num(size.get("estimated_market_value")), _num(size.get("fund_scale")))
    factors = []

    def log_score(value: float, *, floor_log: float, scale: float) -> float:
        if value <= 0:
            return 0.0
        return max(0.0, min(100.0, (math.log10(value) - floor_log) * scale))

    amount_score = log_score(amount, floor_log=4.0, scale=17.0)
    volume_score = log_score(volume, floor_log=4.0, scale=15.0)
    size_score = log_score(market_value, floor_log=7.0, scale=13.0)
    if amount > 0:
        factors.append("liquidity:amount")
    if volume > 0:
        factors.append("liquidity:volume")
    if market_value > 0:
        factors.append("size:available")
    if mode == "amount":
        return amount_score, factors
    if mode == "volume":
        return volume_score, factors
    if mode == "size":
        return size_score, factors
    return max(amount_score, (amount_score + volume_score) / 2.0), factors


def _text_score(record: dict[str, Any], query: str) -> tuple[float, list[str]]:
    q_text = norm_text(query)
    q_ascii = norm_ascii(query)
    code = str(record.get("code") or "")
    name = str(record.get("name") or "")
    names = [name] + [str(v) for v in record.get("aliases", []) if v]
    initials = [str(v) for v in record.get("pinyin_initials", []) if v]
    ascii_aliases = [str(v) for v in record.get("ascii_aliases", []) if v]
    sectors = [str(v) for v in record.get("sectors", []) if v]

    code_norm = norm_ascii(code)
    code_like = _is_code_like_query(query, q_ascii)
    if code_like and q_ascii == code_norm:
        return 100.0, [f"code_exact:{code}"]
    if code_like and q_ascii in code_norm and len(q_ascii) >= 3:
        return 88.0, [f"code_contains:{query}"]

    for value in names:
        n = norm_text(value)
        if q_text and q_text == n:
            return _apply_variant_penalty(95.0, [f"name_exact:{value}"], n, q_text)
        if q_text and n.startswith(q_text):
            return _apply_variant_penalty(85.0, [f"name_prefix:{query}"], n, q_text)
        if q_text and q_text in n:
            return _apply_variant_penalty(75.0, [f"name_substring:{query}"], n, q_text)

    if code_like:
        for value in initials:
            n = norm_ascii(value)
            if q_ascii and q_ascii == n:
                return 95.0, [f"pinyin_initials_exact:{q_ascii}"]
            if q_ascii and n.startswith(q_ascii) and len(q_ascii) >= 2:
                return 85.0, [f"pinyin_initials_prefix:{q_ascii}"]

        for value in ascii_aliases:
            n = norm_ascii(value)
            if q_ascii and q_ascii == n:
                return 92.0, [f"alias_ascii:{q_ascii}"]
            if q_ascii and n.startswith(q_ascii) and len(q_ascii) >= 2:
                return 82.0, [f"alias_ascii_prefix:{q_ascii}"]

    for value in sectors:
        n = norm_text(value)
        if q_text and q_text in n:
            return 62.0, [f"sector_match:{value}"]
    return 0.0, []


def _passes_filters(
    record: dict[str, Any],
    markets: list[str],
    types: list[str],
    sectors: list[str],
    include_external: bool,
) -> bool:
    market = str(record.get("market") or "").upper()
    if not include_external and market in EXTERNAL_MARKETS:
        return False
    if markets and market not in {m.upper() for m in markets}:
        return False
    typ = str(record.get("instrument_type") or "unknown").lower()
    if types and typ not in {t.lower() for t in types}:
        return False
    if sectors:
        rec_sectors = {str(s) for s in record.get("sectors", [])}
        if not rec_sectors.intersection(set(sectors)):
            return False
    return True


def _rank_score(
    record: dict[str, Any], score: float, rank_by: str, prefer_types: list[str] | None = None
) -> tuple[float, list[str]]:
    factors = []
    quote = str(record.get("quote_supported") or "unknown")
    quote_bonus = {"true": 8.0, "unknown": 0.0, "false": -12.0}.get(quote, 0.0)
    factors.append(f"quote_supported:{quote}")
    typ = str(record.get("instrument_type") or "unknown").lower()
    type_bonus = TYPE_ORDER.get(typ, 0) * 0.7
    if prefer_types and typ in [t.lower() for t in prefer_types]:
        idx = [t.lower() for t in prefer_types].index(typ)
        type_bonus += max(0.0, 9.0 - idx * 3.0)
        factors.append(f"type_preference:{typ}")
    else:
        factors.append(f"type:{typ}")
    market = str(record.get("market") or "").upper()
    external_penalty = -10.0 if market in EXTERNAL_MARKETS else 0.0
    if external_penalty:
        factors.append(f"external_market:{market}")
    metric, metric_factors = _metric_score(record, rank_by)
    factors.extend(metric_factors or ["liquidity:missing"])

    if rank_by == "relevance":
        final = score + quote_bonus + external_penalty
    elif rank_by in {"liquidity", "amount", "volume"}:
        final = score * 0.55 + metric * 0.45 + quote_bonus + type_bonus + external_penalty
    elif rank_by == "size":
        final = score * 0.60 + metric * 0.40 + quote_bonus + type_bonus + external_penalty
    else:
        final = score * 0.70 + metric * 0.18 + quote_bonus + type_bonus + external_penalty
    return round(max(0.0, min(100.0, final)), 2), factors


def result_record(
    record: dict[str, Any],
    score: float,
    rank_score: float,
    match_reason: list[str],
    rank_factors: list[str],
    include_metrics: bool,
) -> dict[str, Any]:
    item = {
        "code": record.get("code", ""),
        "name": record.get("name", ""),
        "market": record.get("market", ""),
        "instrument_type": record.get("instrument_type", "unknown"),
        "sectors": list(record.get("sectors", []))[:20],
        "score": score,
        "rank_score": rank_score,
        "match_reason": match_reason,
        "rank_factors": rank_factors,
        "quote_supported": record.get("quote_supported", "unknown"),
        "next_tools": ["qmt_xtdata_snapshot", "qmt_xtdata_bars", "qmt_xtdata_instrument_detail"],
        "warnings": [],
    }
    if include_metrics:
        item["liquidity"] = record.get("liquidity", {}) if isinstance(record.get("liquidity"), dict) else {}
        item["size"] = record.get("size", {}) if isinstance(record.get("size"), dict) else {}
    if item["quote_supported"] != "true":
        item["warnings"].append(
            "quote support is not confirmed; inspect detail or ask the user before using quote tools"
        )
    return item


def _liquidity_tiebreak(item: dict[str, Any]) -> float:
    liquidity = item.get("liquidity") if isinstance(item.get("liquidity"), dict) else {}
    return max(
        _num(liquidity.get("latest_amount")),
        _num(liquidity.get("avg_amount_20d")),
        _num(liquidity.get("avg_amount_5d")),
        _num(liquidity.get("latest_volume")),
        _num(liquidity.get("avg_volume_20d")),
    )


def search_records(
    cache: dict[str, Any],
    query: str,
    *,
    sectors: list[str] | None = None,
    markets: list[str] | None = None,
    types: list[str] | None = None,
    include_external: bool = False,
    limit: int = 20,
    rank_by: str = "combined",
    include_metrics: bool = True,
    prefer_types: list[str] | None = None,
    min_score: float = 1.0,
) -> dict[str, Any]:
    clean = validate_query(query, limit, "never", rank_by)
    clean_sectors = validate_filters(sectors, "sectors")
    clean_markets = validate_filters(markets, "markets")
    clean_types = validate_filters(types, "types")
    prefer = validate_filters(prefer_types, "prefer_types") if prefer_types else []

    hits = []
    for record in cache.get("records", []):
        if not isinstance(record, dict):
            continue
        if not _passes_filters(record, clean_markets, clean_types, clean_sectors, include_external):
            continue
        score, reasons = _text_score(record, clean)
        if score < min_score:
            continue
        final, factors = _rank_score(record, score, rank_by, prefer)
        hits.append(result_record(record, score, final, reasons, factors, include_metrics))

    hits.sort(key=lambda item: (item["rank_score"], item["score"], _liquidity_tiebreak(item)), reverse=True)
    return {
        "results": hits[:limit],
        "truncated": len(hits) > limit,
    }


def search_sectors(cache: dict[str, Any], query: str, *, limit: int = 50) -> dict[str, Any]:
    clean = validate_query(query, limit, "never", "relevance")
    q_text = norm_text(clean)
    q_ascii = norm_ascii(clean)
    hits = []
    for sector in cache.get("sector_names", []):
        name = str(sector)
        score = 0.0
        reason = []
        n_text = norm_text(name)
        n_ascii = norm_ascii(name)
        if q_text == n_text or q_ascii == n_ascii:
            score, reason = 100.0, [f"exact:{clean}"]
        elif q_text and q_text in n_text:
            score, reason = 85.0, [f"substring:{clean}"]
        elif q_ascii and q_ascii in n_ascii:
            score, reason = 75.0, [f"ascii_substring:{clean}"]
        if score:
            hits.append({"name": name, "score": score, "match_reason": reason})
    hits.sort(key=lambda item: item["score"], reverse=True)
    return {"sectors": hits[:limit], "truncated": len(hits) > limit}


def resolve_from_results(results: list[dict[str, Any]], min_score: float) -> dict[str, Any]:
    if not results:
        return {
            "resolved": False,
            "confidence": "low",
            "best": None,
            "alternates": [],
            "guidance": "No candidate matched. Ask the user for a more specific name, code, sector, or ETF theme instead of inventing a code.",
        }
    best = results[0]
    alternates = results[1:]
    ambiguous = bool(alternates and alternates[0]["rank_score"] >= best["rank_score"] - 5)
    if best["score"] < min_score:
        confidence = "low"
        resolved = False
    elif ambiguous:
        confidence = "ambiguous"
        resolved = False
    elif best["rank_score"] >= 85:
        confidence = "high"
        resolved = True
    else:
        confidence = "medium"
        resolved = True
    guidance = "Use the best candidate code with qmt_xtdata_snapshot or qmt_xtdata_bars."
    if not resolved:
        guidance = "Candidates are low-confidence or ambiguous. Inspect alternates or ask the user to clarify before calling quote tools."
    elif best.get("quote_supported") != "true":
        guidance = "Best candidate metadata was found, but quote support is not confirmed. Prefer quote-supported alternates or ask the user to clarify."
    elif best.get("instrument_type") == "etf":
        guidance = "Use the best ETF candidate for observable/tradable exposure, then call qmt_xtdata_snapshot or qmt_xtdata_bars."
    return {
        "resolved": resolved,
        "confidence": confidence,
        "best": best,
        "alternates": alternates,
        "guidance": guidance,
    }
