# Feature Specification: Account-Query Tools (xttrade, read-only)

**Status**: Draft (planned; local validation blocked)
**Depends on**: 002 (MCP core), 005 (trader auto-connect)

**Local validation blocker**: broker must enable the MiniQMT/xttrader
programmatic trading/query permission for the account. In the current operator
environment this appears not to be opened yet, likely because the account does
not meet the broker's threshold. The feature is still required for users who do
have permission; local tests will cover disabled/not-authorized behavior until a
permissioned account is available. Market data (003) is unaffected.

## Summary

Expose read-only xttrader query tools as an opt-in tool family for deployments
where broker permission is available: assets, positions, orders, trades, credit
details, IPO quota, account list, etc. NO write/trade tools are exposed in this
feature. Without permission, 002 health/capabilities report
`xttrade_query: not_authorized` or `disabled`, and operators still get a clear
diagnosis rather than a broken server.

## User Scenarios

### US0 - Operator sees account-query capability is unavailable locally (P0 / current reality)
**Acceptance**:
1. Given `xttrader.connect()` fails because broker permission is not enabled, then `/healthz` and `qmt_capabilities` report `xttrade_query: not_authorized` or `disabled`.
2. Given permission is not enabled, then account-query tools are absent from tool discovery by default, or clearly refuse with `not_authorized` if explicitly enabled for diagnosis.

### US1 - Permissioned user reads account state (P1)
**Acceptance**:
1. Given a permissioned account, QMT logged in, and account-query tools enabled, when the agent calls the asset-query tool with an allow-listed account, then it returns structured cash/total/market-value/frozen.
2. Given positions/orders/trades query tools, then each returns a structured list.
3. Given trader connection drops, then tools return `trader-not-ready` and health flips out of connected state.

### US2 - Account safety (P2)
**Acceptance**:
1. Queries are restricted to accounts present in the resolved config's account list/allowlist; an unknown account id yields a refusal.
2. No write/trade tool is exposed in readonly mode.

## Functional Requirements

- **FR-001**: Read-only query tools: stock asset, positions, orders (+cancelable filter), trades, position statistics, credit detail/contracts/subjects/slo/assure, new-purchase limit, IPO data, account infos/status, OTC fund/position, smt query quoter/compact.
- **FR-002**: Structured outputs for each account object; no raw SDK object passthrough.
- **FR-003**: Account-type enum (STOCK/CREDIT/FUTURE); account-id format validation.
- **FR-004**: Server-side account allow-list; the agent cannot widen it via args (fail-closed).
- **FR-005**: Trader-readiness aware: if `xttrader.connect()` is not established, query tools return `trader-not-ready` cleanly.
- **FR-006**: Absolutely no order/cancel/transfer/borrow/export tools in this feature (read-only only).
- **FR-007**: Every query is audited (account, tool, outcome) per 002.
- **FR-008**: When broker permission is missing, the account-query family MUST be disabled or marked `not_authorized`; it MUST NOT look like a broken-but-enabled production tool family.
- **FR-009**: Account-query tools MUST be behind an explicit enable flag and an account allow-list; installing the package alone MUST NOT expose account data.
- **FR-010**: A permissioned deployment MUST be able to enable read-only query tools without enabling any write/trade tool.

## Success Criteria

- **SC-001**: With broker permission granted, asset/positions/orders queries return correct structured data for an allow-listed account.
- **SC-002**: An account id not on the allow-list is refused 100% of the time.
- **SC-003**: With trader not ready, tools degrade gracefully (no crash, clear error).
- **SC-004**: In an unpermissioned environment, health/capabilities clearly report `not_authorized` or `disabled`, and the MCP core remains healthy.

## Out of Scope / Deferred

- Order placement / cancel / fund transfer / securities borrowing (separate guarded feature).
- Real-time order/trade push callbacks.

## Assumptions / Dependencies

- **Broker permission** (`m_nPythonConnectNet`/程序化交易) MUST be granted to validate successful account-query paths; without it, only disabled/refusal behavior can be tested locally.
- 005 auto-connects the trader and feeds readiness to 002's health.
- account id(s) configured in broker.yaml (mcp.accounts / allowlist).
