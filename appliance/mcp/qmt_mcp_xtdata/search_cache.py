"""Persistent instrument-search cache built from xtdata metadata."""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qmt_mcp_core.errors import McpCoreError

from .search_seed import seed_records
from .serializers import bars_rows, json_clean, snapshot_records

SCHEMA_VERSION = 1
DEFAULT_CACHE_PATH = Path(os.environ.get("QMT_INSTRUMENT_CACHE_PATH", "/broker/cache/instrument-search-v1.json"))
DEFAULT_SECTORS = ["沪深A股", "京市A股", "沪深ETF", "沪深指数"]
EXTERNAL_SECTOR_KEYWORDS = ("香港", "港股", "联交所", "美股")
TTL_SECONDS = int(os.environ.get("QMT_INSTRUMENT_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))

CallXtdata = Callable[..., Any]


def now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def cache_path(path: str | None = None) -> Path:
    p = Path(path or os.environ.get("QMT_INSTRUMENT_CACHE_PATH", str(DEFAULT_CACHE_PATH)))
    normalized = str(p).replace("\\", "/")
    if normalized == "/broker" or normalized.startswith("/broker/"):
        return p
    if os.environ.get("QMT_MCP_TEST_MODE") == "1" or "pytest" in os.environ.get("PYTEST_CURRENT_TEST", ""):
        return p
    raise McpCoreError("validation", "instrument cache path must live under /broker", {"path": str(p)})


def load_cache(path: str | None = None) -> dict[str, Any] | None:
    p = cache_path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise McpCoreError("dependency", f"failed to read instrument cache: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise McpCoreError("dependency", "instrument cache has unsupported schema", {"path": str(p)})
    return data


def empty_cache(broker_id: str = "unknown", path: str | None = None) -> dict[str, Any]:
    ts = now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "broker_id": broker_id,
        "cache_path": str(cache_path(path)),
        "created_at": ts,
        "updated_at": ts,
        "source_sectors": [],
        "sector_names": [],
        "records": [],
        "partial": False,
        "errors": [],
        "uses_seed": True,
    }


def cache_state(cache: dict[str, Any] | None) -> dict[str, Any]:
    if not cache:
        return {"exists": False, "state": "missing", "record_count": 0, "sector_count": 0, "uses_seed": True}
    updated = str(cache.get("updated_at") or "")
    age = None
    state = "unknown"
    try:
        dt = datetime.fromisoformat(updated)
        age = max(0, int(time.time() - dt.timestamp()))
        state = "fresh" if age <= TTL_SECONDS else "stale"
    except Exception:
        state = "unknown"
    return {
        "exists": True,
        "state": state,
        "updated_at": updated,
        "age_seconds": age,
        "ttl_seconds": TTL_SECONDS,
        "record_count": len(cache.get("records", [])),
        "sector_count": len(cache.get("sector_names", [])),
        "source_sectors": list(cache.get("source_sectors", [])),
        "partial": bool(cache.get("partial")),
        "uses_seed": bool(cache.get("uses_seed", True)),
        "cache_path": str(cache.get("cache_path") or DEFAULT_CACHE_PATH),
    }


class FileLock:
    def __init__(self, path: Path, timeout: float = 30):
        self.path = path
        self.timeout = timeout
        self.fd: int | None = None

    def __enter__(self):
        started = time.time()
        while True:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode("ascii"))
                return self
            except FileExistsError as exc:
                if time.time() - started > self.timeout:
                    raise McpCoreError(
                        "capacity", "instrument cache refresh lock is busy", {"lock": str(self.path)}
                    ) from exc
                time.sleep(0.25)

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            os.close(self.fd)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def write_cache(cache: dict[str, Any], path: str | None = None) -> Path:
    p = cache_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(cache, ensure_ascii=False, separators=(",", ":"))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(p.parent), delete=False) as fh:
        fh.write(payload)
        tmp = Path(fh.name)
    os.replace(tmp, p)
    return p


def is_stale(cache: dict[str, Any] | None) -> bool:
    return cache_state(cache).get("state") in {"missing", "stale", "unknown"}


def with_seed_records(cache: dict[str, Any]) -> dict[str, Any]:
    seeded = dict(cache)
    records = [record for record in seeded.get("records", []) if isinstance(record, dict)]
    seeded["records"] = merge_records(records + seed_records(now_iso()))
    existing_sectors = {str(sector) for sector in seeded.get("sector_names", [])}
    record_sectors = {str(sector) for record in seeded["records"] for sector in record.get("sectors", [])}
    seeded["sector_names"] = sorted(existing_sectors | record_sectors)
    seeded["uses_seed"] = True
    return seeded


def market_of(code: str) -> str:
    return code.rsplit(".", 1)[-1].upper() if "." in code else ""


def quote_supported(code: str) -> str:
    return "true" if market_of(code) in {"SH", "SZ", "BJ"} else "unknown"


def _gbk_initial(ch: str) -> str:
    if not ch:
        return ""
    if ch.isascii():
        return ch.upper() if ch.isalnum() else ""
    ranges = [
        (-20319, "A"),
        (-20283, "B"),
        (-19775, "C"),
        (-19218, "D"),
        (-18710, "E"),
        (-18526, "F"),
        (-18239, "G"),
        (-17922, "H"),
        (-17417, "J"),
        (-16474, "K"),
        (-16212, "L"),
        (-15640, "M"),
        (-15165, "N"),
        (-14922, "O"),
        (-14914, "P"),
        (-14630, "Q"),
        (-14149, "R"),
        (-14090, "S"),
        (-13318, "T"),
        (-12838, "W"),
        (-12556, "X"),
        (-11847, "Y"),
        (-11055, "Z"),
    ]
    try:
        raw = ch.encode("gbk")
        if len(raw) < 2:
            return ""
        value = raw[0] * 256 + raw[1] - 65536
    except Exception:
        return ""
    letter = ""
    for boundary, initial in ranges:
        if value >= boundary:
            letter = initial
        else:
            break
    return letter


def pinyin_initials(value: str) -> str:
    return "".join(_gbk_initial(ch) for ch in str(value or ""))


def infer_type(code: str, name: str, sectors: list[str], detail: dict[str, Any]) -> str:
    text = "".join([name, code] + sectors + [str(detail.get("ProductID", ""))]).upper()
    if "ETF" in text or "基金" in text:
        return "etf"
    if "指数" in text or "INDEX" in text:
        return "index"
    if "债" in text or "BOND" in text:
        return "bond"
    if market_of(code) in {"IF", "SF", "DF", "INE", "GF", "ZF"}:
        return "future"
    return "stock" if market_of(code) in {"SH", "SZ", "BJ", "HK"} else "unknown"


def _detail_name(detail: dict[str, Any], code: str) -> str:
    for key in ["InstrumentName", "instrument_name", "name", "Name"]:
        if detail.get(key):
            return str(detail[key])
    return code


def _size_metrics(detail: dict[str, Any], latest_price: float = 0.0) -> dict[str, Any]:
    total = detail.get("TotalVolume") or detail.get("total_volume")
    floating = detail.get("FloatVolume") or detail.get("float_volume")
    size = {"total_volume": total, "float_volume": floating}
    try:
        volume = float(total or floating or 0)
        if volume and latest_price:
            size["estimated_market_value"] = volume * latest_price
    except Exception:
        pass
    return {k: v for k, v in size.items() if v not in (None, "")}


def make_record(code: str, detail: dict[str, Any], sectors: list[str], ts: str) -> dict[str, Any]:
    clean_code = str(code)
    market = market_of(clean_code)
    name = _detail_name(detail, clean_code)
    initials = pinyin_initials(name)
    typ = infer_type(clean_code, name, sectors, detail)
    return {
        "code": clean_code,
        "market": market,
        "name": name,
        "aliases": [],
        "pinyin_initials": [initials] if initials else [],
        "ascii_aliases": [],
        "instrument_type": typ,
        "exchange_id": detail.get("ExchangeID", market),
        "instrument_id": detail.get("InstrumentID", clean_code.split(".", 1)[0]),
        "product_id": detail.get("ProductID", ""),
        "sectors": sorted(set(sectors)),
        "quote_supported": quote_supported(clean_code),
        "metadata_source": "xtdata",
        "updated_at": ts,
        "liquidity": {},
        "size": _size_metrics(detail),
        "raw_fields": detail,
    }


def merge_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        code = str(record.get("code") or "")
        if not code:
            continue
        existing = merged.get(code)
        if existing is None:
            merged[code] = dict(record)
            continue
        # xtdata fields win over seed blanks, but aliases/metrics merge.
        if existing.get("metadata_source") == "seed" and record.get("metadata_source") == "xtdata":
            base, extra = dict(record), existing
        else:
            base, extra = existing, record
        for key in ["aliases", "pinyin_initials", "ascii_aliases", "sectors"]:
            base[key] = sorted({str(v) for v in list(base.get(key, [])) + list(extra.get(key, [])) if v})
        if not base.get("liquidity") and extra.get("liquidity"):
            base["liquidity"] = extra["liquidity"]
        if not base.get("size") and extra.get("size"):
            base["size"] = extra["size"]
        base["metadata_source"] = (
            "merged" if {existing.get("metadata_source"), record.get("metadata_source")} != {"xtdata"} else "xtdata"
        )
        merged[code] = base
    return sorted(merged.values(), key=lambda r: str(r.get("code", "")))


def _refresh_metrics(
    call_xtdata: CallXtdata, records: list[dict[str, Any]], max_metric_codes: int, metrics_count: int, ts: str
) -> None:
    def priority(record: dict[str, Any]) -> tuple[int, str]:
        typ = str(record.get("instrument_type") or "unknown").lower()
        liquidity = record.get("liquidity") if isinstance(record.get("liquidity"), dict) else {}
        if liquidity:
            return (0, str(record.get("code", "")))
        if typ == "etf":
            return (1, str(record.get("code", "")))
        if typ == "index":
            return (2, str(record.get("code", "")))
        return (3, str(record.get("code", "")))

    candidates = [r for r in records if r.get("quote_supported") == "true"]
    candidates.sort(key=priority)
    codes = [r["code"] for r in candidates[:max_metric_codes]]
    if not codes:
        return
    args = (["close", "amount", "volume"], codes, "1d", "", "", metrics_count, "none", True, True)
    try:
        try:
            raw = call_xtdata("get_market_data_ex", *args)
        except Exception:
            raw = call_xtdata("get_market_data_ex", *args[:-1])
        rows = bars_rows(raw, codes, ["close", "amount", "volume"])
    except Exception:
        return
    by_code: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_code.setdefault(str(row.get("code")), []).append(row)
    by_record = {r["code"]: r for r in records}
    updated_codes: set[str] = set()
    for code, code_rows in by_code.items():
        if not code_rows or code not in by_record:
            continue
        amounts = [_safe_float(row.get("amount")) for row in code_rows if _safe_float(row.get("amount")) > 0]
        volumes = [_safe_float(row.get("volume")) for row in code_rows if _safe_float(row.get("volume")) > 0]
        closes = [_safe_float(row.get("close")) for row in code_rows if _safe_float(row.get("close")) > 0]
        if not amounts and not volumes:
            continue
        liquidity = {
            "metrics_updated_at": ts,
            "metrics_source": "bars",
        }
        if amounts:
            liquidity["avg_amount_20d"] = sum(amounts[-20:]) / len(amounts[-20:])
            liquidity["avg_amount_5d"] = sum(amounts[-5:]) / len(amounts[-5:])
            liquidity["latest_amount"] = amounts[-1]
        if volumes:
            liquidity["avg_volume_20d"] = sum(volumes[-20:]) / len(volumes[-20:])
            liquidity["latest_volume"] = volumes[-1]
        by_record[code]["liquidity"] = liquidity
        updated_codes.add(code)
        if closes:
            size = by_record[code].get("size") if isinstance(by_record[code].get("size"), dict) else {}
            size.update(_size_metrics(by_record[code].get("raw_fields", {}), closes[-1]))
            by_record[code]["size"] = size

    missing = [code for code in codes if code not in updated_codes]
    if not missing:
        return
    try:
        ticks = snapshot_records(call_xtdata("get_full_tick", missing), missing)
    except Exception:
        return
    for tick in ticks:
        code = str(tick.get("code") or "")
        if code not in by_record:
            continue
        amount = _safe_float(tick.get("amount"))
        volume = _safe_float(tick.get("volume"))
        if amount <= 0 and volume <= 0:
            continue
        liquidity = by_record[code].get("liquidity") if isinstance(by_record[code].get("liquidity"), dict) else {}
        liquidity = dict(liquidity)
        liquidity["metrics_updated_at"] = ts
        liquidity["metrics_source"] = "snapshot"
        if amount > 0:
            liquidity["latest_amount"] = amount
        if volume > 0:
            liquidity["latest_volume"] = volume
        by_record[code]["liquidity"] = liquidity
        price = _safe_float(tick.get("last_price"))
        if price > 0:
            size = by_record[code].get("size") if isinstance(by_record[code].get("size"), dict) else {}
            size.update(_size_metrics(by_record[code].get("raw_fields", {}), price))
            by_record[code]["size"] = size


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def refresh_cache(
    call_xtdata: CallXtdata,
    *,
    broker_id: str = "unknown",
    sectors: list[str] | None = None,
    include_external: bool = False,
    force: bool = False,
    max_codes: int = 20000,
    refresh_metrics: bool = True,
    metrics_count: int = 20,
    max_metric_codes: int = 500,
    path: str | None = None,
) -> dict[str, Any]:
    if max_codes < 1 or max_codes > 100000:
        raise McpCoreError("validation", "max_codes out of bounds", {"min": 1, "max": 100000})
    p = cache_path(path)
    with FileLock(p.with_suffix(p.suffix + ".lock")):
        if not force:
            existing = load_cache(path)
            if existing and not is_stale(existing):
                return existing
        ts = now_iso()
        cache = empty_cache(broker_id, path)
        errors = []
        try:
            try:
                call_xtdata("download_sector_data")
            except Exception:
                pass
            sector_names = json_clean(call_xtdata("get_sector_list")) or []
            if not isinstance(sector_names, list):
                sector_names = []
            cache["sector_names"] = [str(s) for s in sector_names]
        except Exception as exc:
            errors.append({"stage": "sector_list", "error": f"{type(exc).__name__}: {exc}"})
            sector_names = []

        selected = sectors or DEFAULT_SECTORS
        if include_external:
            selected = list(selected) + [s for s in sector_names if any(k in str(s) for k in EXTERNAL_SECTOR_KEYWORDS)]
        selected = list(dict.fromkeys(str(s) for s in selected if s))

        code_sectors: dict[str, list[str]] = {}
        for sector in selected:
            try:
                codes = json_clean(call_xtdata("get_stock_list_in_sector", sector, -1)) or []
                if not isinstance(codes, list):
                    continue
                for code in codes:
                    clean = str(code)
                    if not include_external and market_of(clean) not in {"SH", "SZ", "BJ"}:
                        continue
                    if len(code_sectors) >= max_codes and clean not in code_sectors:
                        break
                    code_sectors.setdefault(clean, []).append(sector)
            except Exception as exc:
                errors.append({"stage": "sector", "sector": sector, "error": f"{type(exc).__name__}: {exc}"})

        records: list[dict[str, Any]] = []
        for code, rec_sectors in code_sectors.items():
            try:
                detail = json_clean(call_xtdata("get_instrument_detail", code, False)) or {}
                if not isinstance(detail, dict):
                    detail = {}
                records.append(make_record(code, detail, rec_sectors, ts))
            except Exception as exc:
                errors.append({"stage": "detail", "code": code, "error": f"{type(exc).__name__}: {exc}"})

        records.extend(seed_records(ts))
        records = merge_records(records)
        if refresh_metrics:
            _refresh_metrics(call_xtdata, records, max_metric_codes, metrics_count, ts)

        cache.update(
            {
                "updated_at": ts,
                "source_sectors": selected,
                "records": records,
                "partial": bool(errors),
                "errors": errors[:100],
                "uses_seed": True,
            }
        )
        write_cache(cache, path)
        return cache


def usable_cache_or_seed(broker_id: str = "unknown", path: str | None = None) -> dict[str, Any]:
    cache = load_cache(path)
    if cache:
        return with_seed_records(cache)
    cache = empty_cache(broker_id, path)
    records = seed_records(now_iso())
    cache["records"] = records
    cache["sector_names"] = sorted({str(sector) for record in records for sector in record.get("sectors", [])})
    cache["partial"] = True
    cache["errors"] = [{"stage": "cache", "error": "cache missing; using seed records only"}]
    return cache
