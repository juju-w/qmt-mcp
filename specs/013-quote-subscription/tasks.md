# Tasks: Quote Prefetch Subscriptions

## Phase A — Model & Limits

- [ ] T001 Define subscription model fields: codes, period, backend preference,
  fallback polling settings, enabled, label/group metadata, created_at/updated_at,
  xtdata subscription ids, and last update status.
- [ ] T002 Add validators for period/backend enum, subscription-count limits,
  fallback interval bounds, max codes, and cache policy.
- [ ] T003 Implement hot quote cache with freshness metadata and stale checks.
- [ ] T004 Implement JSON subscription store under `/broker/cache`.

## Phase B — Official Subscription Runtime

- [ ] T005 Implement lifecycle manager for official `xtdata.subscribe_quote`
  registrations and `xtdata.unsubscribe_quote` cleanup.
- [ ] T006 Normalize `subscribe_quote` callback payloads into the hot quote cache.
- [ ] T007 Track active backend diagnostics in health: enabled/degraded, backend,
  code count, subscription ids, last callback time, last error.
- [ ] T008 Ensure xtdata-not-ready, capacity, callback, unsubscribe, and
  validation errors degrade cleanly without crashing MCP.
- [ ] T009 Add optional `subscribe_whole_quote` backend for explicitly configured
  broad/full-push workloads, with no implicit full-market default.

## Phase C — Polling Fallback

- [ ] T010 Implement bounded fallback scheduler using existing worker/readiness
  patterns.
- [ ] T011 Refresh fallback-enabled subscriptions with existing xtdata snapshot
  call path when official subscription is unavailable or stale.
- [ ] T012 Expose fallback reason and freshness separately from official callback
  metadata.

## Phase D — MCP Tools

- [ ] T013 Register `qmt_xtdata_quote_subscribe` for add/update/idempotent
  subscription writes.
- [ ] T014 Register `qmt_xtdata_quote_unsubscribe`.
- [ ] T015 Register `qmt_xtdata_quote_subscriptions` list/read tool.
- [ ] T016 Register `qmt_xtdata_quote_subscription_status`.
- [ ] T017 Extend `qmt_xtdata_snapshot` with `cache_policy=prefer|cache_only|live`
  and cache source/freshness metadata.
- [ ] T018 Audit subscription management, callback failures, fallback refresh
  failures, and unsubscribe failures without logging raw quote payloads.

## Phase E — Optional DB Aggregation

- [ ] T019 Add minute-bar accumulator for quote updates.
- [ ] T020 When DB marketdata is enabled, upsert compact 1m bars through the 012
  warehouse path.
- [ ] T021 Verify DB outage leaves hot cache updates working and marks health
  degraded.

## Phase F — CLI & Docs

- [ ] T022 Add qmtctl subscription commands: add/update/remove/list/status.
- [ ] T023 Add qmtctl snapshot cache flags (`--cache-policy`, plus convenient
  `--live`/`--cache-only` if useful).
- [ ] T024 Update README and quickstart docs with subscription workflows,
  official-subscription limits, fallback behavior, and storage/scale expectations.

## Phase G — Tests & Verification

- [ ] T025 Unit-test hot cache freshness, stale/missing behavior, and latest-only
  storage.
- [ ] T026 Unit-test subscription store persistence and idempotent updates.
- [ ] T027 Unit-test fake `subscribe_quote` callback cache updates and
  `unsubscribe_quote` cleanup.
- [ ] T028 Unit-test polling fallback activation and stale-callback diagnostics.
- [ ] T029 Unit-test cache-aware snapshot policies.
- [ ] T030 Unit-test qmtctl command-to-tool mappings.
- [ ] T031 Run host CI tier: ruff, format, pytest, Go test/vet/build.
- [ ] T032 NAS/manual smoke: add subscription, observe official backend callback
  status, read cached snapshot, remove subscription and verify unsubscribe.
