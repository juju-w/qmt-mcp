# Feature Specification: Portfolio Risk Analysis

**Status**: Draft
**Depends on**: 003 (xtdata snapshot/bars), 004 (read-only xttrade account-query),
006 (instrument search metadata), 007 (qmtctl CLI), 012 (optional DB warehouse),
013 (quote prefetch cache, optional but recommended).

## Summary

Add read-only portfolio analysis tools that combine account holdings from
xttrade with market data from xtdata to produce actionable, structured risk
metrics for an agent or operator. The feature turns raw account/position data
into account-level and position-level summaries: market value, cash ratio,
unrealized P&L, concentration, exposure by market/type/sector when metadata is
available, stale quote diagnostics, and simple guardrail checks.

This is **analysis only**. It MUST NOT place, cancel, recommend, or automate
trades. It should help the user understand current portfolio state and risk
drivers, then leave decisions to the user.

This feature is implemented as an MCP tool family plus qmtctl commands, not as a
Codex/local skill. A future skill may sit on top of these tools to explain or
format results, but the account access, allowlist enforcement, audit trail, and
metric calculations live in the MCP service.

## User Scenarios

### US1 - Account summary from positions and quotes (P1)

**Acceptance**: Given an allow-listed account with positions and xtdata quotes
available, when the agent calls the portfolio summary tool, then it returns cash,
total assets, market value, position count, quote coverage, unrealized P&L, top
positions, and timestamp/freshness metadata.

### US2 - Concentration and exposure breakdown (P1)

**Acceptance**: Given a portfolio with multiple holdings, the analysis reports
largest position weights, top-N concentration, market/type exposure, and
available sector/theme exposure using the instrument search cache/metadata. If
sector metadata is missing, the response includes a clear partial-data note.

### US3 - Risk guardrails without trading actions (P1)

**Acceptance**: Given configurable thresholds such as max single-position weight,
max top-5 weight, min cash ratio, and max stale quote age, the tool returns
violations/warnings but never creates orders or changes account state.

### US4 - Works with quote cache when available (P2)

**Acceptance**: Given 013 quote prefetch is enabled for portfolio holdings, the
analysis uses fresh cached snapshots by default and falls back to live xtdata
according to an explicit quote policy. Returned metrics identify whether quotes
came from cache, live xtdata, or were missing/stale.

### US5 - CLI operator workflow (P2)

**Acceptance**: `qmtctl portfolio summary --account <id>` and related commands
return human-readable output by default and full structured JSON with `--json`.

## Functional Requirements

- **FR-001**: The feature MUST be read-only and must only call existing read-only
  account-query and market-data paths.
- **FR-002**: Add MCP tools:
  `qmt_portfolio_summary`, `qmt_portfolio_positions`,
  `qmt_portfolio_exposure`, and `qmt_portfolio_risk_checks`.
- **FR-003**: Every account-scoped tool MUST require `account_id` and MUST rely on
  the server-side 004 allowlist. The agent cannot widen account access.
- **FR-004**: The summary MUST include asset totals when available, position
  market values, weights, unrealized P&L, quote freshness, and partial-data
  diagnostics.
- **FR-005**: Position valuation MUST use explicit quote policy:
  `prefer_cache`, `live`, or `cache_only`. Missing/stale quotes MUST not silently
  produce zero valuations.
- **FR-006**: Exposure breakdown MUST support market and instrument type using
  code/metadata, and SHOULD support sector/theme exposure when the 006 cache has
  usable metadata.
- **FR-007**: Risk checks MUST accept caller-provided thresholds with conservative
  defaults and return structured pass/warn/fail checks. They MUST NOT include
  trading instructions.
- **FR-008**: Outputs MUST include calculation metadata: source tools, timestamps,
  quote policy, missing quote count, stale quote count, and any unavailable data
  families.
- **FR-009**: Health/capabilities MUST report portfolio analysis as disabled or
  degraded when xttrade query, xtdata, or required metadata are unavailable.
- **FR-010**: `qmtctl` MUST expose portfolio commands for summary, positions,
  exposure, and risk checks.
- **FR-011**: All portfolio tool calls MUST be audited with account id and bounded
  summary metadata; raw full position/quote payloads SHOULD NOT be written to
  audit logs.
- **FR-012**: Host tests MUST cover calculations with fake positions/quotes,
  missing quotes, stale quotes, unknown account refusal, and threshold warnings.

## Metric Definitions

- **Position market value**: latest quote price multiplied by usable holding
  volume, unless xttrade already provides a trusted market value. When both exist,
  include both or note reconciliation differences.
- **Position weight**: position market value divided by total portfolio market
  value or total asset value, as specified in the response metadata.
- **Unrealized P&L**: current market value minus cost basis when cost basis is
  available from xttrade serializers.
- **Cash ratio**: available cash or cash asset divided by total assets when asset
  data is available.
- **Concentration**: max single-position weight and cumulative top-N weight.
- **Quote coverage**: positions with fresh quote divided by total positions.

## Success Criteria

- **SC-001**: With fake account assets, positions, and quotes, host tests
  reproduce deterministic summary metrics and risk checks.
- **SC-002**: With an account not in the allowlist, portfolio tools refuse before
  any account or quote data is returned.
- **SC-003**: Missing/stale quotes are surfaced as partial diagnostics and do not
  become zero-valued positions.
- **SC-004**: `qmtctl portfolio summary --account <id> --json` returns the same
  structured payload as the MCP tool.
- **SC-005**: In a permissioned NAS/manual environment, the summary completes for
  a real allow-listed account without exposing write tools.

## Out of Scope

- Order placement, cancellation, portfolio rebalancing automation, or trade
  recommendations.
- A Codex skill that directly reads account data or reimplements portfolio
  metrics outside the MCP service. Skills may only consume the MCP outputs as an
  optional explanation/reporting layer.
- Regulatory suitability scoring.
- Full backtesting or strategy execution; that can be a later analysis/sandbox
  feature if needed.
- Intraday VaR-grade quantitative risk models. v1 focuses on explainable
  holdings, exposure, concentration, P&L, and guardrails.

## Assumptions

- 004 may be disabled or not authorized on some broker accounts. In that case
  portfolio analysis reports unavailable/disabled rather than pretending to work.
- 013 is recommended for low-latency quote freshness but not mandatory; live
  xtdata can be used.
- Sector/theme exposure is best-effort and depends on the quality of 006 metadata.
