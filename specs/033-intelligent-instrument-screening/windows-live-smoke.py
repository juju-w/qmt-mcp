"""Read-only Windows/QMT smoke for feature 033.

This script is intentionally independent of launcher configuration and account
data. It imports a staged MCP source tree plus the broker-provided xtquant SDK,
then optionally runs bounded market-data screens. It never downloads data,
starts QMT, touches xttrade, or places orders.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

CORE_ETF_CODES = (
    "510500.SH",
    "512500.SH",
    "159922.SZ",
    "513500.SH",
    "515000.SH",
    "516500.SH",
)
COMPLEX_ETF_CODES = (
    "513130.SH",
    "513180.SH",
    "159740.SZ",
    "513330.SH",
    "159920.SZ",
    "513500.SH",
)
COMPLEX_STOCK_CODES = (
    "600519.SH",
    "000858.SZ",
    "300750.SZ",
    "601899.SH",
    "002594.SZ",
    "600276.SH",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-root", type=Path, required=True)
    parser.add_argument("--xtquant-root", type=Path, required=True)
    parser.add_argument("--as-of", default="")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--suite", choices=("core", "complex", "all"), default="core")
    return parser.parse_args()


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str))


def instrument_record(call_xtdata: Any, code: str, asset_type: str) -> dict[str, Any]:
    detail = call_xtdata("get_instrument_detail", code, False) or {}
    if not isinstance(detail, dict):
        detail = {}
    name = next(
        (str(detail[key]) for key in ("InstrumentName", "instrument_name", "name", "Name") if detail.get(key)),
        code,
    )
    return {
        **detail,
        "code": code,
        "name": name,
        "instrument_type": asset_type,
        "market": code.rsplit(".", 1)[-1],
        "open_date": detail.get("OpenDate") or detail.get("open_date") or "",
        "is_trading": True,
    }


def result_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "screen_id": result["screen_id"],
        "universe": result["universe"],
        "stage_counts": result["stage_counts"],
        "coverage": result["coverage"],
        "cache": result["cache"],
        "data_context": result["data_context"],
        "warnings": result["warnings"],
        "results": result["results"],
    }


def explanation_summary(explanation: dict[str, Any] | None) -> dict[str, Any] | None:
    if not explanation:
        return None
    return {
        "screen_id": explanation["screen_id"],
        "code": explanation["code"],
        "name": explanation["name"],
        "state": explanation["state"],
        "rank": explanation["rank"],
        "score": explanation["score"],
        "coverage": explanation["coverage"],
        "rank_contributions": explanation["rank_contributions"],
    }


def error_summary(exc: Exception, *, source_call_delta: int) -> dict[str, Any]:
    return {
        "error_type": getattr(exc, "error_type", type(exc).__name__),
        "message": getattr(exc, "message", str(exc)),
        "details": getattr(exc, "details", None),
        "source_call_delta": source_call_delta,
    }


def edge_explanations(service: Any, result: dict[str, Any]) -> list[dict[str, Any]]:
    codes = [row["code"] for row in result["results"]]
    selected = list(dict.fromkeys(codes[:1] + codes[-1:]))
    return [explanation_summary(service.explain(result["screen_id"], code)) for code in selected]


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(args.mcp_root))
    sys.path.append(str(args.xtquant_root))

    try:
        from xtquant import xtdata

        from qmt_mcp_screening.cache import FactorObservationCache, ScreenResultStore
        from qmt_mcp_screening.catalog import catalog_for
        from qmt_mcp_screening.service import ScreeningService, UniverseResolver
        from qmt_mcp_screening.sources import ScreeningSource
        from qmt_mcp_xtdata.serializers import bars_rows
    except Exception as exc:
        emit(
            {
                "ok": False,
                "stage": "import",
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        )
        return 2

    capability_methods = {
        "daily_bars": "get_market_data_ex",
        "snapshot": "get_full_tick",
        "instrument_detail": "get_instrument_detail",
        "financial_data": "get_financial_data",
    }
    capabilities = {name for name, method in capability_methods.items() if callable(getattr(xtdata, method, None))}
    probe = {
        "ok": True,
        "stage": "probe" if args.probe_only else "live",
        "python": sys.version.split()[0],
        "xtdata_module": str(Path(xtdata.__file__).resolve()),
        "capabilities": sorted(capabilities),
        "catalog": {
            "etf_available": sum(
                row["availability"] == "available"
                for row in catalog_for("etf", capabilities=capabilities, include_unavailable=True)
            ),
            "stock_available": sum(
                row["availability"] == "available"
                for row in catalog_for("stock", capabilities=capabilities, include_unavailable=True)
            ),
        },
    }
    if args.probe_only:
        emit(probe)
        return 0
    if not args.as_of:
        emit(
            {
                **probe,
                "ok": False,
                "stage": "arguments",
                "message": "--as-of is required for live mode",
            }
        )
        return 2

    try:
        calls: Counter[str] = Counter()

        def call_xtdata(name: str, *values: Any) -> Any:
            calls[name] += 1
            return getattr(xtdata, name)(*values)

        etf_codes: set[str] = set()
        stock_codes: set[str] = set()
        if args.suite in {"core", "all"}:
            etf_codes.update(CORE_ETF_CODES)
            stock_codes.add("600519.SH")
        if args.suite in {"complex", "all"}:
            etf_codes.update(COMPLEX_ETF_CODES)
            stock_codes.update(COMPLEX_STOCK_CODES)

        records = [instrument_record(call_xtdata, code, "etf") for code in sorted(etf_codes)]
        records.extend(instrument_record(call_xtdata, code, "stock") for code in sorted(stock_codes))

        def sector_members(sector: str) -> list[str] | None:
            try:
                values = call_xtdata("get_stock_list_in_sector", sector, -1)
            except TypeError:
                values = call_xtdata("get_stock_list_in_sector", sector)
            return [str(code) for code in values] if isinstance(values, list) else None

        def read_bars(**kwargs: Any) -> dict[str, Any]:
            values = (
                kwargs["fields"],
                kwargs["codes"],
                kwargs["period"],
                kwargs["start_time"],
                kwargs["end_time"],
                kwargs["count"],
                kwargs["dividend_type"],
                kwargs["fill_data"],
                kwargs["enable_read_from_server"],
            )
            try:
                raw = call_xtdata("get_market_data_ex", *values)
            except TypeError:
                raw = call_xtdata("get_market_data_ex", *values[:-1])
            return {
                "ok": True,
                "rows": bars_rows(raw, kwargs["codes"], kwargs["fields"]),
            }

        resolver = UniverseResolver(
            cache_provider=lambda: {"records": records, "partial": False},
            sector_provider=sector_members,
            max_codes=100,
        )
        source = ScreeningSource(
            call_xtdata,
            broker_id="windows-smoke",
            capabilities=capabilities,
            read_bars=read_bars,
        )
        service = ScreeningService(
            resolver=resolver,
            source=source,
            factor_cache=FactorObservationCache(max_items=1000),
            result_store=ScreenResultStore(max_items=50),
            limits={
                "max_universe_codes": 100,
                "max_factor_refs": 12,
                "max_results": 10,
            },
        )
        suites: dict[str, Any] = {}

        if args.suite in {"core", "all"}:
            etf_request = {
                "asset_type": "etf",
                "etf_profile": "broad_market_equity",
                "as_of": args.as_of,
                "universe": {
                    "kind": "exposure",
                    "values": ["csi_500"],
                    "policy": "require_complete",
                },
                "filters": [
                    {
                        "factor": {
                            "factor_id": "avg_amount",
                            "params": {"window": 20},
                        },
                        "operator": "gte",
                        "value": 1,
                    }
                ],
                "rank": [
                    {
                        "factor": {
                            "factor_id": "avg_amount",
                            "params": {"window": 20},
                        },
                        "weight": 1,
                    }
                ],
                "limit": 5,
            }
            etf_first = service.screen(etf_request)
            etf_repeat = service.screen(etf_request)

            stock_request = {
                "asset_type": "stock",
                "stock_profile": "non_financial",
                "as_of": args.as_of,
                "universe": {
                    "kind": "codes",
                    "values": ["600519.SH"],
                    "policy": "require_complete",
                },
                "rank": [
                    {
                        "factor": {"factor_id": "listing_days", "params": {}},
                        "weight": 1,
                    }
                ],
                "limit": 1,
            }
            stock = service.screen(stock_request)
            suites["core"] = {
                "strict_etf": result_summary(etf_first),
                "repeat_cache": etf_repeat["cache"],
                "explanations": edge_explanations(service, etf_first),
                "narrow_stock": result_summary(stock),
                "stock_explanations": edge_explanations(service, stock),
            }

        if args.suite in {"complex", "all"}:
            strict_universe = resolver.resolve(
                asset_type="etf",
                universe={
                    "kind": "exposure",
                    "values": ["HSTECH"],
                    "policy": "require_complete",
                },
            )
            cross_border_request = {
                "asset_type": "etf",
                "etf_profile": "cross_border_equity",
                "as_of": args.as_of,
                "universe": {
                    "kind": "exposure",
                    "values": ["HSTECH"],
                    "policy": "require_complete",
                },
                "filters": [
                    {
                        "factor": {"factor_id": "listing_days", "params": {}},
                        "operator": "gte",
                        "value": 120,
                    }
                ],
                "rank_missing_policy": "neutral",
                "rank": [
                    {
                        "factor": {"factor_id": "listing_days", "params": {}},
                        "weight": 0.10,
                        "direction": "higher",
                    },
                    {
                        "factor": {"factor_id": "return", "params": {"window": 20}},
                        "weight": 0.20,
                        "direction": "higher",
                    },
                    {
                        "factor": {"factor_id": "return", "params": {"window": 60}},
                        "weight": 0.10,
                        "direction": "higher",
                    },
                    {
                        "factor": {
                            "factor_id": "annualized_volatility",
                            "params": {"window": 20},
                        },
                        "weight": 0.10,
                        "direction": "lower",
                    },
                    {
                        "factor": {
                            "factor_id": "max_drawdown",
                            "params": {"window": 60},
                        },
                        "weight": 0.10,
                        "direction": "higher",
                    },
                    {
                        "factor": {
                            "factor_id": "avg_amount",
                            "params": {"window": 20},
                        },
                        "weight": 0.40,
                        "direction": "higher",
                    },
                ],
                "limit": 5,
                "diagnostics": "detailed",
            }
            cross_border = service.screen(cross_border_request)
            cross_border_repeat = service.screen(cross_border_request)

            stock_request = {
                "asset_type": "stock",
                "stock_profile": "non_financial",
                "as_of": args.as_of,
                "universe": {
                    "kind": "codes",
                    "values": list(COMPLEX_STOCK_CODES),
                    "name": "跨行业质量、成长、动量与流动性篮子",
                    "policy": "require_complete",
                },
                "filters": [
                    {
                        "factor": {"factor_id": "listing_days", "params": {}},
                        "operator": "gte",
                        "value": 250,
                    }
                ],
                "rank_missing_policy": "neutral",
                "rank": [
                    {
                        "factor": {"factor_id": "listing_days", "params": {}},
                        "weight": 0.10,
                        "direction": "higher",
                    },
                    {
                        "factor": {"factor_id": "roe_ttm", "params": {}},
                        "weight": 0.20,
                        "direction": "higher",
                    },
                    {
                        "factor": {"factor_id": "revenue_growth_yoy", "params": {}},
                        "weight": 0.15,
                        "direction": "higher",
                    },
                    {
                        "factor": {"factor_id": "debt_to_assets", "params": {}},
                        "weight": 0.15,
                        "direction": "lower",
                    },
                    {
                        "factor": {"factor_id": "return", "params": {"window": 20}},
                        "weight": 0.15,
                        "direction": "higher",
                    },
                    {
                        "factor": {
                            "factor_id": "annualized_volatility",
                            "params": {"window": 20},
                        },
                        "weight": 0.10,
                        "direction": "lower",
                    },
                    {
                        "factor": {
                            "factor_id": "avg_amount",
                            "params": {"window": 20},
                        },
                        "weight": 0.15,
                        "direction": "higher",
                    },
                ],
                "limit": 6,
                "diagnostics": "detailed",
            }
            stock = service.screen(stock_request)
            stock_repeat = service.screen(stock_request)

            def guarded_failure(request: dict[str, Any]) -> dict[str, Any]:
                before = sum(calls.values())
                try:
                    service.screen(request)
                except Exception as exc:
                    return error_summary(exc, source_call_delta=sum(calls.values()) - before)
                return {
                    "error_type": None,
                    "message": "unexpected success",
                    "source_call_delta": 0,
                }

            historical_snapshot = guarded_failure(
                {
                    "asset_type": "etf",
                    "etf_profile": "cross_border_equity",
                    "as_of": args.as_of,
                    "universe": {
                        "kind": "exposure",
                        "values": ["HSTECH"],
                        "policy": "require_complete",
                    },
                    "rank": [
                        {
                            "factor": {"factor_id": "bid_ask_spread_bps", "params": {}},
                            "weight": 1,
                            "missing_policy": "fail",
                        }
                    ],
                    "limit": 3,
                }
            )
            unknown_exposure = guarded_failure(
                {
                    "asset_type": "etf",
                    "etf_profile": "cross_border_equity",
                    "as_of": args.as_of,
                    "universe": {
                        "kind": "exposure",
                        "values": ["AI-dream-index-2049"],
                        "policy": "require_complete",
                    },
                    "rank": [
                        {
                            "factor": {"factor_id": "listing_days", "params": {}},
                            "weight": 1,
                        }
                    ],
                    "limit": 3,
                }
            )
            if historical_snapshot["error_type"] != "capability" or historical_snapshot["source_call_delta"]:
                raise AssertionError("historical snapshot guard did not fail before source access")
            if unknown_exposure["error_type"] != "validation" or unknown_exposure["source_call_delta"]:
                raise AssertionError("unknown exposure guard did not fail before source access")

            suites["complex"] = {
                "candidate_names": {
                    record["code"]: record["name"] for record in records if record["code"] in COMPLEX_ETF_CODES
                },
                "strict_hang_seng_tech_codes": strict_universe["codes"],
                "cross_border_multifactor": result_summary(cross_border),
                "cross_border_repeat_cache": cross_border_repeat["cache"],
                "cross_border_explanations": edge_explanations(service, cross_border),
                "stock_quality_growth_momentum": result_summary(stock),
                "stock_repeat_cache": stock_repeat["cache"],
                "stock_explanations": edge_explanations(service, stock),
                "guardrails": {
                    "historical_snapshot": historical_snapshot,
                    "unknown_exposure": unknown_exposure,
                },
            }

        forbidden_calls = sorted(
            name
            for name in calls
            if name.startswith("download_")
            or "formula" in name.lower()
            or "xttrade" in name.lower()
            or "order" in name.lower()
        )
        if forbidden_calls:
            raise AssertionError(f"forbidden source calls observed: {forbidden_calls}")
    except Exception as exc:
        emit(
            {
                **probe,
                "ok": False,
                "stage": "live-screen",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "source_errors": getattr(locals().get("source"), "errors", []),
                "call_counts": dict(sorted(locals().get("calls", {}).items())),
            }
        )
        return 1

    emit(
        {
            **probe,
            "suite": args.suite,
            "suites": suites,
            "call_counts": dict(sorted(calls.items())),
            "forbidden_calls": forbidden_calls,
            "source_errors": source.errors,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
