# Feature Specification: xtdata Reference Data

**Status**: Draft
**Depends on**: 003 (xtdata market-data tools), 006 (instrument search), 007
(qmtctl CLI), 012 (optional DB warehouse).

## Summary

Expose the optional read-only xtdata reference-data APIs that were deferred from
003: financial statements, dividend factors, IPO/new-share information,
convertible-bond reference data, ETF creation/redemption metadata, available
periods, and static-data downloads where the SDK requires a local cache refresh.

This feature is pure read-only. It never creates sectors, writes QMT local
watchlists, places trades, submits IPO orders, or changes account state.

## User Scenarios

### US1 - Retrieve financial statement tables (P1)

**Acceptance**: Given xtdata supports financial data, when an agent requests a
bounded stock list, table list, date range, and report type, then the response
returns JSON-clean rows grouped by code and table with source timestamps and
partial-data diagnostics.

### US2 - Fetch IPO/new-share reference data (P1)

**Acceptance**: Given a date range, when a user asks for new-share subscription
information, then the tool returns stock code, name, market, online subscription
code, issue quantity, subscription limit, price, and valuation fields where
available.

### US3 - Use dividend, ETF, and convertible-bond metadata (P2)

**Acceptance**: An agent can request dividend factors for one code, ETF
creation/redemption data, and convertible-bond info when the runtime supports the
corresponding official APIs. Unsupported APIs return `not_supported` diagnostics.

### US4 - Refresh static reference caches safely (P2)

**Acceptance**: Operators can run bounded maintenance downloads for financial,
ETF, convertible-bond, holiday, or historical-contract metadata. Calls are
worker-backed, audited, and return progress/status, not large raw datasets.

### US5 - qmtctl operator workflow (P2)

**Acceptance**: `qmtctl ref financial`, `qmtctl ref ipo`, `qmtctl ref dividends`,
`qmtctl ref cb`, and `qmtctl ref etf` return readable output by default and full
structured JSON with `--json`.

## Functional Requirements

- **FR-001**: The feature MUST be read-only and MUST NOT expose account-scoped
  IPO submission, trading, transfer, sector mutation, or model execution.
- **FR-002**: Add MCP tools:
  `qmt_xtdata_financial_data`, `qmt_xtdata_download_financial_data`,
  `qmt_xtdata_dividend_factors`, `qmt_xtdata_ipo_info`,
  `qmt_xtdata_download_cb_data`, `qmt_xtdata_cb_info`,
  `qmt_xtdata_download_etf_info`, `qmt_xtdata_etf_info`,
  `qmt_xtdata_download_holiday_data`, `qmt_xtdata_download_history_contracts`,
  and `qmt_xtdata_period_list`.
- **FR-003**: Financial data requests MUST validate code count, table names,
  date range, and `report_type=report_time|announce_time` before calling xtdata.
- **FR-004**: Financial outputs MUST be JSON-clean and grouped by code and table;
  pandas/numpy SDK objects MUST NOT leak to MCP clients.
- **FR-005**: IPO info MUST support bounded `start_time`/`end_time` date ranges
  and normalize common fields such as issue code, subscription code, issue
  quantity, subscription limit, price, profitability flag, and PE values.
- **FR-006**: Dividend-factor requests MUST be one-code or bounded small fanout
  and MUST include date-range metadata.
- **FR-007**: CB/ETF tools MUST capability-gate runtime support and clearly
  distinguish `not_supported`, `not_ready`, empty result, and dependency errors.
- **FR-008**: Download/refresh tools MUST be worker-backed, bounded, audited, and
  return status/progress summaries rather than large raw payloads.
- **FR-009**: Optional DB persistence MAY cache normalized reference rows, but DB
  must remain optional and failures must degrade to direct xtdata responses.
- **FR-010**: qmtctl MUST expose reference-data commands with JSON output for
  downstream scripts.
- **FR-011**: All calls MUST audit code/date/table counts only; full financial
  statement or IPO rows SHOULD NOT be written into audit logs.

## Data Model

### Financial Data Request

- `codes`: bounded list of QMT instrument codes.
- `tables`: bounded list from `Balance`, `Income`, `CashFlow`, `Capital`,
  `Holdernum`, `Top10holder`, `Top10flowholder`, `Pershareindex`.
- `start_time`, `end_time`: optional `YYYYMMDD`.
- `report_type`: `report_time` or `announce_time`.

### Reference Data Response

- `source`: official xtdata function name.
- `generated_at`: MCP response timestamp.
- `capabilities`: supported/missing function flags.
- `rows` or grouped `data`: normalized records.
- `diagnostics`: missing tables, unsupported functions, truncated rows, and SDK
  dependency errors.

## Success Criteria

- **SC-001**: Fake xtdata tests cover financial data, financial download,
  dividend factors, IPO info, CB, ETF, and period-list serialization.
- **SC-002**: Invalid tables, oversized code lists, and invalid date ranges are
  rejected before xtdata calls.
- **SC-003**: Missing optional APIs return structured not-supported diagnostics.
- **SC-004**: qmtctl reference commands map to the same MCP tools and support
  structured JSON output.
- **SC-005**: Existing 003 market-data tool behavior remains unchanged when 016
  is disabled or optional APIs are unavailable.

## Out of Scope

- IPO subscription/order submission.
- Custom sector creation or mutation.
- Formula/model/factor execution.
- Vendor data outside official xtdata.
- Long-term financial warehouse schema beyond optional 012-compatible caching.

## Assumptions

- Some broker packs may omit optional reference APIs or require a prior download.
- xttrade IPO tools already expose account/query-side IPO data; this feature adds
  xtdata range-based IPO reference data and does not replace xttrade account
  limits.
