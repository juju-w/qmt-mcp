# Tasks: Quote Prefetch Subscriptions

## Phase A — Model & Limits

- [ ] T001 Define subscription model fields: codes, interval_seconds, enabled,
  label/group metadata, created_at/updated_at, last refresh status.
- [ ] T002 Add validators for interval bounds, max codes, and cache policy.
- [ ] T003 Implement hot quote cache with freshness metadata and stale checks.
- [ ] T004 Implement JSON subscription store under `/broker/cache`.

## Phase B — Refresh Runtime

- [ ] T005 Implement bounded refresh scheduler using existing worker/readiness
  patterns.
- [ ] T006 Refresh enabled subscriptions with existing xtdata snapshot call path.
- [ ] T007 Track refresh diagnostics in health: enabled/degraded, code count,
  last refresh, last error.
- [ ] T008 Ensure xtdata-not-ready, capacity, and validation errors degrade
  cleanly without crashing MCP.

## Phase C — MCP Tools

- [ ] T009 Register `qmt_xtdata_quote_subscribe` for add/update/idempotent
  subscription writes.
- [ ] T010 Register `qmt_xtdata_quote_unsubscribe`.
- [ ] T011 Register `qmt_xtdata_quote_subscriptions` list/read tool.
- [ ] T012 Register `qmt_xtdata_quote_subscription_status`.
- [ ] T013 Extend `qmt_xtdata_snapshot` with `cache_policy=prefer|cache_only|live`
  and cache source/freshness metadata.
- [ ] T014 Audit subscription management and refresh failures without logging raw
  quote payloads.

## Phase D — Optional DB Aggregation

- [ ] T015 Add minute-bar accumulator for refreshed snapshots.
- [ ] T016 When DB marketdata is enabled, upsert compact 1m bars through the 012
  warehouse path.
- [ ] T017 Verify DB outage leaves hot cache refresh working and marks health
  degraded.

## Phase E — CLI & Docs

- [ ] T018 Add qmtctl subscription commands: add/update/remove/list/status.
- [ ] T019 Add qmtctl snapshot cache flags (`--cache-policy`, plus convenient
  `--live`/`--cache-only` if useful).
- [ ] T020 Update README and quickstart docs with subscription workflows and
  storage/scale expectations.

## Phase F — Tests & Verification

- [ ] T021 Unit-test hot cache freshness, stale/missing behavior, and latest-only
  storage.
- [ ] T022 Unit-test subscription store persistence and idempotent updates.
- [ ] T023 Unit-test cache-aware snapshot policies.
- [ ] T024 Unit-test qmtctl command-to-tool mappings.
- [ ] T025 Run host CI tier: ruff, format, pytest, Go test/vet/build.
- [ ] T026 NAS/manual smoke: add subscription, observe refresh status, read cached
  snapshot, remove subscription.
