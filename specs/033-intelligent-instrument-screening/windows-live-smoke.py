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
from pathlib import Path
from typing import Any

ETF_CODES = (
    "510500.SH",
    "512500.SH",
    "159922.SZ",
    "513500.SH",
    "515000.SH",
    "516500.SH",
)
STOCK_CODES = ("600519.SH",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-root", type=Path, required=True)
    parser.add_argument("--xtquant-root", type=Path, required=True)
    parser.add_argument("--as-of", default="")
    parser.add_argument("--probe-only", action="store_true")
    return parser.parse_args()


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str))


def instrument_record(xtdata: Any, code: str, asset_type: str) -> dict[str, Any]:
    detail = xtdata.get_instrument_detail(code, False) or {}
    if not isinstance(detail, dict):
        detail = {}
    name = next(
        (
            str(detail[key])
            for key in ("InstrumentName", "instrument_name", "name", "Name")
            if detail.get(key)
        ),
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
    capabilities = {
        name
        for name, method in capability_methods.items()
        if callable(getattr(xtdata, method, None))
    }
    probe = {
        "ok": True,
        "stage": "probe" if args.probe_only else "live",
        "python": sys.version.split()[0],
        "xtdata_module": str(Path(xtdata.__file__).resolve()),
        "capabilities": sorted(capabilities),
        "catalog": {
            "etf_available": sum(
                row["availability"] == "available"
                for row in catalog_for(
                    "etf", capabilities=capabilities, include_unavailable=True
                )
            ),
            "stock_available": sum(
                row["availability"] == "available"
                for row in catalog_for(
                    "stock", capabilities=capabilities, include_unavailable=True
                )
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
        records = [instrument_record(xtdata, code, "etf") for code in ETF_CODES]
        records.extend(instrument_record(xtdata, code, "stock") for code in STOCK_CODES)

        def call_xtdata(name: str, *values: Any) -> Any:
            return getattr(xtdata, name)(*values)

        def sector_members(sector: str) -> list[str] | None:
            try:
                values = xtdata.get_stock_list_in_sector(sector, -1)
            except TypeError:
                values = xtdata.get_stock_list_in_sector(sector)
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
                raw = xtdata.get_market_data_ex(*values)
            except TypeError:
                raw = xtdata.get_market_data_ex(*values[:-1])
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
            factor_cache=FactorObservationCache(max_items=100),
            result_store=ScreenResultStore(max_items=10),
            limits={"max_universe_codes": 100, "max_factor_refs": 8, "max_results": 10},
        )
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
                    "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                    "operator": "gte",
                    "value": 1,
                }
            ],
            "rank": [
                {
                    "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
                    "weight": 1,
                }
            ],
            "limit": 5,
        }
        etf_first = service.screen(etf_request)
        etf_repeat = service.screen(etf_request)
        first_code = etf_first["results"][0]["code"] if etf_first["results"] else ""
        explanation = (
            service.explain(etf_first["screen_id"], first_code) if first_code else None
        )

        stock_request = {
            "asset_type": "stock",
            "stock_profile": "non_financial",
            "as_of": args.as_of,
            "universe": {
                "kind": "codes",
                "values": list(STOCK_CODES),
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
        stock_code = stock["results"][0]["code"] if stock["results"] else ""
        stock_explanation = (
            service.explain(stock["screen_id"], stock_code) if stock_code else None
        )
    except Exception as exc:
        emit(
            {
                **probe,
                "ok": False,
                "stage": "live-screen",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "source_errors": getattr(locals().get("source"), "errors", []),
            }
        )
        return 1

    emit(
        {
            **probe,
            "strict_etf": result_summary(etf_first),
            "repeat_cache": etf_repeat["cache"],
            "explanation": {
                "screen_id": explanation["screen_id"],
                "code": explanation["code"],
                "state": explanation["state"],
                "rank": explanation["rank"],
                "coverage": explanation["coverage"],
            }
            if explanation
            else None,
            "narrow_stock": result_summary(stock),
            "stock_explanation": {
                "screen_id": stock_explanation["screen_id"],
                "code": stock_explanation["code"],
                "state": stock_explanation["state"],
                "rank": stock_explanation["rank"],
                "coverage": stock_explanation["coverage"],
            }
            if stock_explanation
            else None,
            "source_errors": source.errors,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
