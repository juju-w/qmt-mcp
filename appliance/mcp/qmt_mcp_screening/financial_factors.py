"""Point-in-time financial timelines and non-financial stock factors."""

from __future__ import annotations

import re
from typing import Any

from .catalog import factor_definition
from .models import FactorObservation, finite_number

DATE_RE = re.compile(r"^[0-9]{8}$")

TABLE_ALIASES = {
    "income": "Income",
    "利润表": "Income",
    "cashflow": "CashFlow",
    "cash_flow": "CashFlow",
    "现金流量表": "CashFlow",
    "balance": "Balance",
    "balancesheet": "Balance",
    "资产负债表": "Balance",
    "capital": "Capital",
}

FIELD_ALIASES = {
    "report_date": ("report_date", "m_timetag", "reportDate", "end_date"),
    "announce_time": ("announce_time", "m_anntime", "announceDate", "announcement_time"),
    "revenue": ("revenue", "营业总收入", "operating_revenue", "total_revenue"),
    "net_profit": ("net_profit", "归母净利润", "net_profit_parent", "np_parent_company_owners"),
    "gross_profit": ("gross_profit", "毛利润"),
    "operating_cost": ("operating_cost", "营业成本", "cost_of_revenue"),
    "operating_cash_flow": ("operating_cash_flow", "经营活动产生的现金流量净额", "net_operate_cash_flow"),
    "total_assets": ("total_assets", "资产总计", "tot_assets"),
    "total_liabilities": ("total_liabilities", "负债合计", "tot_liab"),
    "equity": ("equity", "归母股东权益", "equity_parent", "total_equity_parent"),
    "float_shares": ("float_shares", "流通股本", "circulating_capital"),
    "total_shares": ("total_shares", "总股本", "total_capital"),
}


class TimelineError(ValueError):
    """Raised when broker financial rows cannot form a deterministic timeline."""


def _canonical_table(name: str) -> str:
    return TABLE_ALIASES.get(str(name).replace(" ", "").lower(), str(name))


def _alias_value(row: dict[str, Any], field: str) -> Any:
    for alias in FIELD_ALIASES.get(field, (field,)):
        if alias in row and row[alias] not in {None, ""}:
            return row[alias]
    return None


def _date(value: Any) -> str:
    normalized = str(value or "").replace("-", "")[:8]
    if not DATE_RE.fullmatch(normalized):
        raise TimelineError(f"malformed financial date: {value!r}")
    return normalized


class FinancialTimeline:
    """Immutable announcement-filtered view of cumulative financial statements."""

    def __init__(self, tables: dict[str, Any], *, as_of: str):
        self.as_of = _date(as_of)
        normalized: dict[str, tuple[dict[str, Any], ...]] = {}
        for raw_name, raw_rows in (tables or {}).items():
            table = _canonical_table(raw_name)
            if not isinstance(raw_rows, (list, tuple)):
                continue
            versions: dict[tuple[str, str], dict[str, Any]] = {}
            for raw in raw_rows:
                if not isinstance(raw, dict):
                    raise TimelineError(f"malformed financial row in {table}")
                report_date = _date(_alias_value(raw, "report_date"))
                announce_time = _date(_alias_value(raw, "announce_time"))
                if announce_time > self.as_of:
                    continue
                row = dict(raw)
                row["report_date"] = report_date
                row["announce_time"] = announce_time
                for field in FIELD_ALIASES:
                    if field in {"report_date", "announce_time"}:
                        continue
                    value = _alias_value(raw, field)
                    if value is not None:
                        row[field] = value
                key = (report_date, announce_time)
                previous = versions.get(key)
                if previous is not None and previous != row:
                    raise TimelineError(f"conflicting duplicate financial row: {table} {key}")
                versions[key] = row

            latest_by_period: dict[str, dict[str, Any]] = {}
            for row in versions.values():
                current = latest_by_period.get(row["report_date"])
                if current is None or row["announce_time"] > current["announce_time"]:
                    latest_by_period[row["report_date"]] = row
            normalized[table] = tuple(
                sorted(latest_by_period.values(), key=lambda item: (item["report_date"], item["announce_time"]))
            )
        self._tables = normalized

    def rows(self, table: str) -> tuple[dict[str, Any], ...]:
        return tuple(dict(row) for row in self._tables.get(_canonical_table(table), ()))

    def latest(self, table: str) -> dict[str, Any] | None:
        rows = self._tables.get(_canonical_table(table), ())
        return dict(rows[-1]) if rows else None

    def previous(self, table: str) -> dict[str, Any] | None:
        rows = self._tables.get(_canonical_table(table), ())
        return dict(rows[-2]) if len(rows) >= 2 else None

    def report(self, table: str, report_date: str) -> dict[str, Any] | None:
        normalized = _date(report_date)
        for row in self._tables.get(_canonical_table(table), ()):
            if row["report_date"] == normalized:
                return dict(row)
        return None

    def value(self, table: str, report_date: str, field: str) -> float | None:
        row = self.report(table, report_date)
        return finite_number(row.get(field)) if row else None

    def ttm(self, table: str, field: str) -> float | None:
        latest = self.latest(table)
        if latest is None:
            return None
        current = finite_number(latest.get(field))
        if current is None:
            return None
        report_date = latest["report_date"]
        if report_date.endswith("1231"):
            return current
        year = int(report_date[:4])
        prior_fiscal = self.value(table, f"{year - 1}1231", field)
        prior_comparable = self.value(table, f"{year - 1}{report_date[4:]}", field)
        if prior_fiscal is None or prior_comparable is None:
            return None
        return current + prior_fiscal - prior_comparable

    def comparable_values(self, table: str, field: str) -> tuple[float, float] | None:
        latest = self.latest(table)
        if latest is None:
            return None
        current = finite_number(latest.get(field))
        prior = self.value(table, f"{int(latest['report_date'][:4]) - 1}{latest['report_date'][4:]}", field)
        if current is None or prior is None:
            return None
        return current, prior

    def latest_announcement(self) -> str:
        announcements = [row["announce_time"] for rows in self._tables.values() for row in rows]
        return max(announcements, default="")


def _missing(
    code: str,
    factor_id: str,
    reason: str,
    timeline: FinancialTimeline,
    *,
    status: str = "missing",
) -> FactorObservation:
    return FactorObservation.missing(
        code=code,
        factor_id=factor_id,
        params={},
        reason=reason,
        status=status,
        unit=factor_definition(factor_id).unit,
        data_as_of=timeline.as_of,
        source="xtdata.financial",
    )


def _available(code: str, factor_id: str, value: float, timeline: FinancialTimeline) -> FactorObservation:
    return FactorObservation.available(
        code=code,
        factor_id=factor_id,
        params={},
        value=value,
        unit=factor_definition(factor_id).unit,
        data_as_of=timeline.as_of,
        source="xtdata.financial",
        announcement_time=timeline.latest_announcement(),
    )


def _positive_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _growth(values: tuple[float, float] | None) -> float | None:
    if values is None:
        return None
    current, prior = values
    if prior <= 0 or current * prior < 0:
        return None
    return current / prior - 1


def calculate_financial_factor(
    *,
    code: str,
    factor_id: str,
    timeline: FinancialTimeline,
    market_cap: float | None,
    stock_profile: str,
) -> FactorObservation:
    """Calculate one point-in-time ordinary-company factor."""

    if stock_profile != "non_financial":
        return _missing(code, factor_id, "profile_incompatible", timeline, status="not_applicable")

    profit = timeline.ttm("Income", "net_profit")
    revenue = timeline.ttm("Income", "revenue")
    latest_balance = timeline.latest("Balance") or {}
    equity = finite_number(latest_balance.get("equity"))
    assets = finite_number(latest_balance.get("total_assets"))
    liabilities = finite_number(latest_balance.get("total_liabilities"))

    if factor_id == "earnings_yield_ttm":
        value = _positive_ratio(profit, market_cap)
    elif factor_id == "pb_mrq":
        value = _positive_ratio(market_cap, equity)
    elif factor_id == "roe_ttm":
        latest_report = str(latest_balance.get("report_date") or "")
        previous_report = f"{int(latest_report[:4]) - 1}{latest_report[4:]}" if DATE_RE.fullmatch(latest_report) else ""
        previous_balance = timeline.report("Balance", previous_report) if previous_report else None
        previous_balance = previous_balance or {}
        previous_equity = finite_number(previous_balance.get("equity"))
        average_equity = (
            (equity + previous_equity) / 2
            if equity is not None and previous_equity is not None and min(equity, previous_equity) > 0
            else None
        )
        value = _positive_ratio(profit, average_equity)
    elif factor_id == "revenue_growth_yoy":
        value = _growth(timeline.comparable_values("Income", "revenue"))
    elif factor_id == "net_profit_growth_yoy":
        value = _growth(timeline.comparable_values("Income", "net_profit"))
    elif factor_id == "gross_margin_ttm":
        gross_profit = timeline.ttm("Income", "gross_profit")
        if gross_profit is None:
            operating_cost = timeline.ttm("Income", "operating_cost")
            gross_profit = revenue - operating_cost if revenue is not None and operating_cost is not None else None
        value = _positive_ratio(gross_profit, revenue)
    elif factor_id == "cfo_to_net_profit_ttm":
        value = _positive_ratio(timeline.ttm("CashFlow", "operating_cash_flow"), profit)
    elif factor_id == "debt_to_assets":
        value = _positive_ratio(liabilities, assets)
    elif factor_id == "asset_growth_yoy":
        value = _growth(timeline.comparable_values("Balance", "total_assets"))
    else:
        return _missing(code, factor_id, "unavailable_capability", timeline)

    if value is None:
        return _missing(code, factor_id, "non_comparable_denominator", timeline)
    if finite_number(value) is None:
        return _missing(code, factor_id, "invalid_source_value", timeline)
    return _available(code, factor_id, value, timeline)
