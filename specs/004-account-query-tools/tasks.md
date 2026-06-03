# Tasks: Account-Query Tools (xttrade, read-only)

`[x]` = done & host-verified · `[~]` = implemented to the documented xttrader
interface, needs a permissioned amd64 account to validate success paths.

## Phase A — Config & health
- [x] T001 `config.py`: `QMT_ENABLE_XTTRADE_QUERY` (default 0), `QMT_TRADE_ACCOUNTS`
  (comma allowlist), `QMT_TRADE_ACCOUNT_TYPE` (STOCK default).
- [x] T002 `health.py`: `xttrade_query` family states (disabled / not_authorized /
  not_ready / enabled) + tool list.

## Phase B — Pure logic (host-testable)
- [x] T003 `accounts.py`: `AccountType` enum (STOCK/CREDIT/FUTURE), account-id
  format validation, server-side `Allowlist` (agent cannot widen; unknown id refused).
- [x] T004 `serializers.py`: structured mappers for asset / position / order /
  trade / account-status (+ a defensive `m_*` raw dump); no raw SDK passthrough.

## Phase C — Session (SDK; unverified)
- [~] T005 `session.py` `TraderSession`: lazy `xttrader` connect handshake
  (`XtQuantTrader(path, session_id).start()/connect()`, subscribe allowlisted
  accounts) returning connected/not_authorized/error for the 005 connector;
  `query(method, account, *args)` that refuses `trader-not-ready` when unconnected.

## Phase D — Tools (gated, read-only)
- [x] T006 `tools.py` core read tools: `qmt_xttrade_asset`, `_positions`,
  `_orders` (+`cancelable_only`), `_trades`, `_account_status`,
  `_position_statistics`, `_new_purchase_limit`, `_ipo_data`. Each: allowlist-check,
  readiness-gate, worker-backed, audited, structured output, rich docstring.
- [x] T007 `app.py`: `register_optional_xttrade(...)` behind flag+allowlist; wire
  `TraderSession.connect` as the connector's real connect_fn when enabled;
  `assert_no_write_tools()` still passes.

## Phase E — Tests (host)
- [x] T008 `test_xttrade_accounts.py` — type enum, id validation, allowlist
  fail-closed (unknown id refused; args cannot widen).
- [x] T009 `test_xttrade_serializers.py` — fake SDK objects -> structured dicts.
- [x] T010 `test_xttrade_gating.py` — disabled/not-ready/not-authorized boundaries;
  no write tools registered.

## Phase F — Verify
- [x] T011 Host: ruff + format + pytest green; build-smoke unaffected (family gated off).
- [~] T012 Permissioned amd64: enable flag + allowlist, QMT logged in with
  programmatic permission -> asset/positions/orders/trades return structured data
  (SC-001); unknown account refused (SC-002); trader-not-ready degrades (SC-003).

## Deferred (broker-specific; need credit/OTC/futures accounts)
- [ ] T013 credit detail/contracts/subjects/slo/assure; OTC fund/position; smt
  quoter/compact. Same pattern; add when a suitable account is available.
