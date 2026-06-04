# Feature Specification: Option Chain & Volatility Inputs

**Status**: Draft
**Depends on**: 003 (xtdata market-data tools), 006 (instrument search), 007
(qmtctl CLI), 013 (quote subscription/cache, recommended).

## Summary

Expose a read-only option-data tool family for option chains, call/put contract
metadata, option quote snapshots, realtime implied volatility where supported,
and volatility-index input packages. The immediate target is to feed external
services that calculate volatility indices for 50/300/500 ETF or index option
families without making those services scrape QMT directly.

This feature provides source data and normalized inputs. It does not place
orders, recommend option trades, or require the MCP service to become the
canonical VIX calculation engine. A later calculation tool may be added if the
formula and validation set are owned in this repo.

## User Scenarios

### US1 - Discover option contracts for an underlying (P1)

**Acceptance**: Given a supported option underlying such as `510050.SH`,
`510300.SH`, `510500.SH`, or another broker-supported option underlying, when an
agent requests the option chain for a date/month, then it receives bounded CALL
and PUT contract lists grouped by expiry and strike.

### US2 - Retrieve normalized call/put quote inputs (P1)

**Acceptance**: Given an option chain, when an agent requests quotes for the
contracts, then the response includes bid/ask, bid/ask volume, last price,
volume, amount, open interest, timestamp, quote freshness, and missing-field
diagnostics for each contract.

### US3 - Feed an external VIX calculation service (P1)

**Acceptance**: Given a supported family such as 50ETF, 300ETF, or 500ETF, when
the agent requests a volatility-index input package, then the response includes
underlying price, eligible expiries, paired call/put rows by strike, midpoint
price fields, risk-free-rate fields when available, quote timestamps, and
provenance so an external VIX service can calculate deterministically.

### US4 - Surface optional IV and BSM helper data (P2)

**Acceptance**: If the installed xtquant exposes `get_option_iv`,
`get_option_detail_data`, `bsm_price`, or `bsm_iv`, the tool family can return
those values with capability metadata. If unavailable, the response marks the
field unsupported rather than failing the whole chain.

### US5 - qmtctl operator workflow (P2)

**Acceptance**: `qmtctl option chain`, `qmtctl option quotes`, and
`qmtctl option vix-inputs` return readable summaries by default and full
structured JSON with `--json`.

## Functional Requirements

- **FR-001**: The feature MUST be read-only and MUST NOT expose option order,
  exercise, cancellation, or strategy execution functions.
- **FR-002**: Add MCP tools:
  `qmt_xtdata_option_underlyings`, `qmt_xtdata_option_chain`,
  `qmt_xtdata_option_detail`, `qmt_xtdata_option_quotes`,
  `qmt_xtdata_option_iv`, and `qmt_xtdata_volatility_index_inputs`.
- **FR-003**: Underlying discovery MUST use official xtdata option APIs when
  available, especially `get_option_undl_data` and `get_option_list`; sector
  fallback is allowed only when capability detection says the direct API is
  missing.
- **FR-004**: Option detail MUST normalize official fields such as option type
  (`CALL`/`PUT`), underlying code/market, exercise price, expiry, contract unit,
  risk-free rate, historical volatility, and trading status.
- **FR-005**: Option quote tools MUST use existing snapshot/full-tick logic or
  013 quote cache for bounded contract lists and MUST include quote source and
  freshness metadata.
- **FR-006**: `qmt_xtdata_volatility_index_inputs` MUST return data inputs only:
  underlying quote, expiry groups, strike rows, call/put contract ids, bid/ask
  midpoints, and data-quality diagnostics. It MUST NOT silently calculate or
  publish an index value unless a future spec defines the formula contract.
- **FR-007**: Built-in family aliases SHOULD include 50ETF, 300ETF, 500ETF,
  科创50ETF, 创业板ETF, and CSI index-option families where the broker pack
  exposes contracts. Operators MUST be able to pass an explicit underlying code
  instead of relying on aliases.
- **FR-008**: Requests MUST enforce bounds for max underlyings, max expiries, max
  contracts, max quote fanout, and stale-quote tolerance before calling xtdata.
- **FR-009**: Runtime capability detection MUST report which option APIs are
  available: chain discovery, detail, quote, IV, BSM helpers, historical
  contracts, and quote subscription/cache integration.
- **FR-010**: Outputs MUST be JSON-clean and stable for downstream calculation:
  no pandas/numpy objects, no localized-only field names, and no unbounded raw
  SDK payloads by default.
- **FR-011**: qmtctl MUST expose option commands for chain/detail/quotes/
  volatility-index inputs.
- **FR-012**: All tool calls MUST be audited with bounded code/count summaries;
  full option-chain payloads SHOULD NOT be written to audit logs.

## Data Model

### Option Contract

- `code`: QMT option code, such as `10005331.SHO` or an IF/IO option code.
- `underlying_code`: normalized underlying instrument code.
- `option_type`: `CALL` or `PUT`.
- `expiry_date`: `YYYYMMDD` when available.
- `exercise_price`: numeric strike.
- `contract_unit`: option contract unit or volume multiple.
- `risk_free_rate`: optional value from official detail fields.
- `historical_volatility`: optional value from official detail fields.
- `is_trading`: best-effort trading status.

### Option Quote

- `code`, `last_price`, `bid_price`, `ask_price`, `bid_volume`, `ask_volume`,
  `volume`, `amount`, `open_interest`, `timestamp`, `source`, `age_ms`.

### Volatility Index Input Package

- `family`: requested alias or underlying code.
- `underlying`: underlying quote and metadata.
- `expiries`: eligible expiry dates with days-to-expiry.
- `strikes`: rows keyed by expiry and strike, containing call/put contracts,
  quotes, midpoints, IV when available, and diagnostics.
- `provenance`: xtdata functions used, quote policy, generated_at, capability
  flags, and missing-data warnings.

## Success Criteria

- **SC-001**: With fake xtdata option APIs, host tests return deterministic chain,
  detail, quote, IV, and volatility-input payloads for a sample 300ETF family.
- **SC-002**: Missing option entitlement or absent xtdata functions produce
  `not_supported`/`not_authorized` diagnostics instead of crashes.
- **SC-003**: A bounded volatility-input request includes paired CALL/PUT rows
  and midpoint fields sufficient for an external VIX calculator.
- **SC-004**: Quote integration can use 013 cache when contracts are subscribed
  and can fall back to live snapshot according to explicit quote policy.
- **SC-005**: qmtctl option commands map to the same MCP tools and support JSON
  output for downstream services.

## Out of Scope

- Option trading, exercise, margin management, or strategy execution.
- Publishing an official VIX/index value from MCP in v1.
- SSE/WebSocket streaming.
- Full raw tick retention for option quotes.
- Non-QMT external option-data vendors.

## Assumptions

- Official xtdata option APIs exist in the installed broker pack but may vary by
  version and entitlement, so capability detection gates all optional functions.
- Some VIX families may be better represented by ETF options, some by index
  options. The tool supports aliases but always returns the resolved underlying
  and contract provenance.
- Existing 003 snapshot tooling can quote option contracts once their codes are
  known.
