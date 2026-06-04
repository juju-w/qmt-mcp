# Feature Specification: Quote Prefetch Subscriptions

**Status**: Draft
**Depends on**: 002 (MCP core + workers + health), 003 (xtdata snapshot/bars),
006 (instrument search), 007 (qmtctl CLI), 012 (optional DB warehouse).

## Summary

Add an opt-in quote prefetch/watchlist layer for instruments the operator or
agent cares about. A new read-only MCP tool family lets clients add, update,
delete, list, and inspect quote subscriptions. A bounded background worker then
refreshes the latest quote snapshot for those instruments at a configured
interval, keeping only the most recent snapshot in a hot in-memory cache.

The goal is **fast reads and lower repeated xtdata latency**, not real-time
client push. v1 does not add SSE/WebSocket quote streaming and does not store
every tick. When 012 PostgreSQL market-data persistence is enabled, the worker
may also aggregate refreshed snapshots into compact 1-minute OHLCV bars; raw
snapshot history is not persisted by default.

Recommended default behavior:

- `qmt_xtdata_snapshot` reads from hot cache for subscribed codes when the cached
  value is fresh enough, annotating `source=quote-cache`, `cached_at`, and
  `age_ms`.
- If a cached value is missing or stale, snapshot falls back to the existing live
  xtdata read path and may refresh the cache.
- A `cache_policy` argument allows explicit `prefer`, `cache_only`, or `live`
  behavior.

## User Scenarios

### US1 - Add a small watchlist and get fast snapshots (P1)

**Acceptance**: Given QMT xtdata is ready, when an agent subscribes 10 instrument
codes at a 5-second interval, then a background worker refreshes their latest
snapshots and later `qmt_xtdata_snapshot` calls return fresh cached values in
milliseconds when available.

### US2 - Manage subscriptions safely (P1)

**Acceptance**: Users can add, update, delete, list, and inspect subscriptions
without exposing any trading/write capability. Unknown or invalid codes are
rejected by the same validators used by xtdata tools. Duplicate adds are
idempotent updates.

### US3 - Degrade cleanly when xtdata is not ready (P1)

**Acceptance**: If QMT login/xtdata becomes unavailable, subscription management
continues to show configured watches, refresh status flips to `not_ready` or
`degraded`, and snapshot reads either return a fresh-enough cached value or a
clear `not_ready`/`stale_cache` error according to cache policy.

### US4 - Optional compact bar aggregation (P2)

**Acceptance**: When the DB warehouse is enabled, refreshed snapshots may be
aggregated into 1-minute bars and upserted into the existing market-data bars
table or a compatible extension table. For 100 subscribed codes over a trading
day, the system should create roughly 24,000 minute-bar rows, not millions of raw
snapshot records.

### US5 - qmtctl operator workflow (P2)

**Acceptance**: `qmtctl` supports subscription commands for create/update/delete/
list/status and snapshot cache policy flags so operators can manage watchlists
without writing raw MCP JSON.

## Functional Requirements

- **FR-001**: The feature MUST be opt-in and read-only. It MUST NOT expose
  trading, order placement, cancellation, transfer, borrow, or export tools.
- **FR-002**: Add subscription management tools:
  `qmt_xtdata_quote_subscribe`, `qmt_xtdata_quote_unsubscribe`,
  `qmt_xtdata_quote_subscriptions`, and `qmt_xtdata_quote_subscription_status`.
- **FR-003**: A subscription MUST include validated `codes`, `interval_seconds`,
  `enabled`, `created_at`, `updated_at`, and last refresh diagnostics. Optional
  metadata may include `label`, `group`, `source`, and `notes`.
- **FR-004**: Subscription changes MUST be persisted across MCP restarts using a
  small JSON file under `/broker` by default, and MAY use PostgreSQL later if 012
  adds a config-domain persistence adapter.
- **FR-005**: A bounded background worker MUST refresh enabled subscriptions using
  existing xtdata snapshot logic. It MUST enforce maximum code count, minimum
  interval, and worker concurrency limits.
- **FR-006**: Hot cache storage MUST keep only the latest snapshot per
  `(broker_id, code)` plus freshness metadata by default. Raw per-refresh history
  MUST NOT be stored unless a future feature explicitly enables retention.
- **FR-007**: `qmt_xtdata_snapshot` MUST support cache-aware reads for subscribed
  codes with `cache_policy` values: `prefer` (default), `cache_only`, and `live`.
  Cached responses MUST include cache metadata so the caller can judge freshness.
- **FR-008**: When cache data is stale, `prefer` MUST fall back to live xtdata when
  possible; `cache_only` MUST return a clear stale/missing-cache error; `live`
  MUST bypass the cache.
- **FR-009**: Optional DB aggregation MUST be compact: aggregate snapshots into
  minute OHLCV bars and upsert them. It MUST NOT write every raw snapshot by
  default.
- **FR-010**: Health/capabilities MUST expose subscription state: disabled,
  enabled, degraded, code count, interval bounds, last refresh time, and last
  error without leaking secrets.
- **FR-011**: `qmtctl` MUST expose subscription commands and snapshot cache-policy
  flags in the CLI.
- **FR-012**: All subscription tool calls and refresh failures MUST be audited with
  sanitized code/count summaries, never large raw quote payloads.

## Scale Guidance

Expected common cases:

- 10 codes refreshed every 5 seconds: tens of MB/day of network payload, but only
  tens of KB hot memory and ~2,400 minute bars/day if DB aggregation is enabled.
- 100 codes refreshed every 5 seconds: roughly hundreds of MB/day of xtdata
  payload, ~300 KB hot memory, and ~24,000 minute bars/day.
- 1,000 codes refreshed every 30 seconds: possible but should require explicit
  higher limits; this is a scanning workload, not the default personal-agent
  watchlist.

Defaults should be conservative: max 100 subscribed codes, min 5-second refresh
interval, max batch size aligned with existing snapshot validation.

## Success Criteria

- **SC-001**: With 10 subscribed codes at 5 seconds, cached snapshot reads return
  in under 50 ms p95 when cache is fresh.
- **SC-002**: With no subscriptions configured, existing xtdata snapshot/bars
  behavior remains unchanged.
- **SC-003**: Restarting MCP preserves the subscription list and resumes refreshes.
- **SC-004**: xtdata outage does not crash the server; health reports degraded and
  cache-only/live/prefer policies behave as specified.
- **SC-005**: For 100 subscribed codes with DB aggregation enabled, one trading day
  writes minute-bar scale rows, not raw snapshot scale rows.

## Out of Scope

- SSE/WebSocket push to clients. This is not part of the current roadmap unless
  future HTTP-compatible clients create a clear need.
- Full-market scanning as a default mode.
- Raw tick-history retention.
- Trading actions or automated order decisions.

## Assumptions

- xtdata snapshot reads are the first implementation path because they already
  exist and are host-testable with fake xtquant. If `xtdata.subscribe_quote`
  proves reliable in a permissioned amd64 environment, it can be used internally
  behind the same subscription/cache interface later.
- The hot cache is process-local. Multi-appliance coordination is out of scope for
  v1.
- 012 DB persistence is optional. Without DB, prefetch still works as in-memory
  acceleration plus persisted subscription config.
