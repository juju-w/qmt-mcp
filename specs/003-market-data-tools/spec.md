# Feature Specification: Market-Data Tools (xtdata)

**Feature Branch**: `003-market-data-tools`

**Created**: 2026-06-03

**Status**: Draft (backlog; depends on 002)

**Input**: User description: "Design the MCP market-data tools from official QMT/XtQuant xtdata documentation. Current broker permission appears to allow xtdata, while xttrade is not opened, so xtdata is the first real tool family."

## Clarifications

### Session 2026-06-03

- **Q1 - Persistence**: Market-data tools do not write results to Postgres in
  this feature. xtdata's own local cache remains the source/cache layer; a later
  persistence feature may warehouse selected data.
- **Q2 - Streaming**: Callback/subscription APIs are deferred. First version is
  bounded request/response only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent Retrieves Snapshot And Bar Data (Priority: P1)

An agent needs current quotes and recent/historical K-line data for A-share,
ETF, index, or other QMT-supported instruments. It calls small validated MCP
tools instead of raw xtdata functions.

**Why this priority**: Snapshot and K-line data are the core value available with
the current permission state and are enough for many analysis workflows.

**Independent Test**: With QMT logged in and xtdata available, request a liquid
stock or ETF snapshot, download a short daily history range, then read bars back
as structured JSON.

**Acceptance Scenarios**:

1. **Given** xtdata is ready, **When** the agent requests full tick/snapshot for valid codes, **Then** it receives structured quote fields per code.
2. **Given** historical bars are not locally cached, **When** the agent runs the download-history tool for a bounded range, **Then** the call completes or returns a structured dependency error.
3. **Given** historical bars are cached, **When** the agent requests bars for a valid code, period, date range, and dividend type, **Then** it receives JSON-clean rows with timestamps and requested fields.
4. **Given** an invalid code, period, date, or oversized request, **When** a tool is called, **Then** it returns a validation error and does not call xtdata.

---

### User Story 2 - Agent Explores Instruments, Sectors, And Calendars (Priority: P2)

An agent needs metadata to build a valid universe: instrument detail, sector
lists, sector constituents, trading days, holidays, and supported periods.

**Why this priority**: Agents need reference data to avoid guessing symbols and
market calendars.

**Independent Test**: Query instrument detail for a known code, list sectors,
fetch sector constituents, and fetch trading dates for a bounded date range.

**Acceptance Scenarios**:

1. **Given** a valid instrument code, **When** the agent requests instrument detail, **Then** it receives a structured contract/instrument record or a not-found result.
2. **Given** sector metadata is available, **When** the agent lists sectors or sector constituents, **Then** it receives bounded structured lists.
3. **Given** a market and date range, **When** the agent requests trading dates or holidays, **Then** it receives normalized date strings.

---

### User Story 3 - Agent Retrieves Optional Reference Data (Priority: P3)

An agent may need financial tables, dividend factors, IPO information,
convertible-bond data, or ETF creation/redemption metadata.

**Why this priority**: These are useful but broader and may be slower or less
uniform across products.

**Independent Test**: Download or request one optional reference data category
for a small bounded universe and confirm structured JSON output or a clear
not-supported/dependency error.

**Acceptance Scenarios**:

1. **Given** financial data is locally available or downloadable, **When** the agent requests a supported financial table, **Then** it receives structured rows.
2. **Given** optional datasets are unsupported by the current xtquant version or broker, **When** requested, **Then** the tool returns a clear not-supported or dependency error.

### Edge Cases

- QMT is not logged in or xtdata cannot connect -> all xtdata tools return `not_ready` without crashing the MCP server.
- Requested history range is too large -> validation refuses or requires explicit larger limits.
- Official xtdata returns pandas/numpy objects -> tool converts to JSON-clean rows.
- Official xtdata returns `None`, empty dict, or empty list -> tool distinguishes not-found, empty data, and dependency failure where possible.
- Subscription/callback APIs are not included in this first feature; continuous streaming is deferred.
- Level2 and投研版特色数据 may require additional entitlement; tools must surface not-supported/not-authorized cleanly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST expose an allow-listed `xtdata` MCP tool family only when 002 reports xtdata capability as available or not-ready.
- **FR-002**: The feature MUST include a snapshot tool backed by the official full-tick/full-push data shape.
- **FR-003**: The feature MUST include a bounded historical/local bar read tool with period, time range, count, fields, and dividend-type validation.
- **FR-004**: The feature MUST include a bounded history-download tool separate from read tools, because xtdata historical reads depend on local cached data.
- **FR-005**: The feature MUST include instrument-detail and instrument-type/reference tools for validating codes and products.
- **FR-006**: The feature MUST include sector-list and sector-constituent tools.
- **FR-007**: The feature MUST include trading-calendar and holiday tools.
- **FR-008**: The feature SHOULD include optional tools for financial data, dividend factors, IPO info, convertible-bond info, and ETF info when supported by the runtime xtquant version.
- **FR-009**: Every xtdata tool MUST validate code format, period enum, date/time format, count/range bounds, and output size limits before calling xtdata.
- **FR-010**: Every xtdata tool MUST return structured JSON-clean outputs and never return pandas/numpy/SDK objects directly.
- **FR-011**: Every blocking xtdata call MUST use the worker/concurrency mechanism defined by 002.
- **FR-012**: Continuous subscription and callback streaming tools MUST NOT be exposed in this feature.
- **FR-013**: Level2 or entitlement-sensitive tools MUST be explicitly marked optional and return not-supported/not-authorized when unavailable.

### Proposed Initial Tool Catalog

- `qmt_xtdata_snapshot`: current full-tick/snapshot for bounded code list.
- `qmt_xtdata_download_history`: populate local cache for one code/period/date range.
- `qmt_xtdata_download_history_batch`: populate local cache for bounded code lists.
- `qmt_xtdata_bars`: read cached/historical bars for bounded code list and period.
- `qmt_xtdata_instrument_detail`: instrument metadata for one code.
- `qmt_xtdata_sector_list`: list sector/category names.
- `qmt_xtdata_sector_constituents`: list codes in one sector.
- `qmt_xtdata_index_weight`: read cached index constituent weights.
- `qmt_xtdata_trading_dates`: trading dates for market/date range.
- `qmt_xtdata_trading_calendar`: normalized trading calendar dates with compatible fallback.
- `qmt_xtdata_holidays`: holiday dates.
- Optional later in this feature if stable: `qmt_xtdata_financial_data`, `qmt_xtdata_dividend_factors`, `qmt_xtdata_ipo_info`, `qmt_xtdata_cb_info`, `qmt_xtdata_etf_info`.

### Key Entities *(include if feature involves data)*

- **Market Data Capability**: The xtdata tool-family state reported through 002.
- **Instrument Code**: A validated QMT code such as `600000.SH` or `000001.SZ`.
- **Period**: A bounded enum for tick/minute/day/week/month and later periods supported by the installed xtquant.
- **Bar Request**: Code list, period, fields, start/end/count, and dividend type.
- **Snapshot Record**: Current quote/tick fields normalized from xtdata output.
- **Reference Dataset**: Instrument, sector, calendar, finance, IPO, CB, ETF, or dividend metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A valid snapshot request for a liquid stock or ETF returns structured JSON within the configured timeout when xtdata is ready.
- **SC-002**: A bounded history download followed by a bar read returns JSON-clean rows without serialization errors.
- **SC-003**: 100% of invalid code/period/date/count inputs are rejected before calling xtdata.
- **SC-004**: No subscription/callback tool appears in the MCP tool list for this feature.
- **SC-005**: If xtdata is unavailable, every xtdata tool returns a uniform `not_ready` or dependency error instead of crashing the server.

## Assumptions

- Feature 002 provides authentication, worker execution, audit logging, error envelopes, and capability gating.
- QMT login is still manual; feature 005 later improves readiness detection and autostart.
- Current operator permission supports xtdata but not xttrade.
- The installed xtquant version may vary by broker pack; optional tools are gated by runtime capability detection.
- Postgres-backed market-data storage is deferred; this feature returns data to
  callers and relies on xtdata/QMT local cache for historical data availability.
