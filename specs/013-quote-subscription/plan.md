# Implementation Plan: Quote Prefetch Subscriptions

**Branch**: `013-quote-subscription` | **Spec**: `specs/013-quote-subscription/spec.md`

## Summary

Implement a read-only quote watchlist/subscription layer. MCP tools manage
subscriptions; the runtime prefers official xtdata quote subscriptions and
normalizes callbacks into an in-memory hot cache; `qmt_xtdata_snapshot` can
prefer that cache for subscribed codes; `qmtctl` exposes the workflow. Bounded
polling through the existing snapshot path remains an explicit fallback when the
broker pack, entitlement, or callback loop cannot support official
subscriptions. Optional DB aggregation can compact quote updates into minute
bars when 012 persistence is enabled.

This is deliberately not SSE push, and SSE compatibility is not part of the
current roadmap.

## Technical Context

**Language/Version**: Python 3.12 for MCP; Go 1.22 for qmtctl.

**Primary Dependencies**: existing FastMCP app, `qmt_mcp_core.WorkerPool`,
xtdata tools/validators, official `xtdata.subscribe_quote` /
`xtdata.unsubscribe_quote`, optional `xtdata.subscribe_whole_quote`, optional
`qmt_mcp_db.Warehouse`.

**Storage**: process-local hot cache; JSON subscription config under `/broker`
by default; optional PostgreSQL minute bars through 012.

**Testing**: pytest unit tests with fake xtquant; existing Go tests for qmtctl;
optional NAS/manual smoke.

**Target Platform**: QMT appliance container; qmtctl on Linux/macOS/Windows.

**Performance Goals**: Fresh cached snapshot reads under 50 ms p95 for small
watchlists; refresh loop must not block MCP request handling.

**Constraints**:

- Read-only only.
- No raw snapshot-history persistence by default.
- Conservative limits: default max 50 official subscriptions, max 100 cached
  watchlist codes with explicit override, min fallback interval 5 seconds.
- Fail gracefully when xtdata is not ready.

**Scale/Scope**: personal-agent and small watchlist workloads first; broad market
scanning requires explicit higher limits and may become a later feature.

## Project Structure

```text
appliance/mcp/qmt_mcp_xtdata/
├── quote_cache.py          # NEW: hot cache + freshness metadata
├── quote_subscriptions.py  # NEW: store + official subscription/fallback manager
├── tools.py                # EDIT: register subscription tools; cache-aware snapshot
└── validation.py           # EDIT if interval/limit validators are added

appliance/mcp/tests/unit/
├── test_quote_cache.py             # NEW
├── test_quote_subscriptions.py     # NEW
└── test_xtdata_quote_tools.py      # NEW/EDIT

cli/qmtctl/internal/qmtctl/
├── cli.go                 # EDIT: subscription commands and snapshot cache flags
└── cli_test.go            # EDIT: command-to-tool mapping tests
```

## Design Decisions

### Hot Cache Shape

Keep latest snapshot per `(broker_id, code)`:

```json
{
  "broker_id": "guangda",
  "code": "510300.SH",
  "snapshot": {"code": "510300.SH", "last_price": 4.965},
  "cached_at": "2026-06-04T09:31:05+0800",
  "age_ms": 1200,
  "source": "quote-prefetch"
}
```

No append-only raw snapshot table in v1.

### Subscription Store

Persist small config JSON under `/broker/cache/quote-subscriptions-v1.json`.
This keeps behavior available even when DB is disabled.

### Subscription Backend Strategy

Use official `xtdata.subscribe_quote` as the primary backend for normal
single-instrument watchlists. Persist the returned subscription id so remove/
disable can call `xtdata.unsubscribe_quote`. Callback payloads update the hot
cache without exposing client push.

Use `xtdata.subscribe_whole_quote` only when the operator explicitly chooses a
broad/full-push workload. It is not the default for personal watchlists.

Use polling via existing snapshot logic only as a fallback backend when official
subscription setup fails, entitlement limits are hit, callbacks stop arriving,
or the installed xtquant lacks the needed function.

### Snapshot Cache Policy

Extend `qmt_xtdata_snapshot` with `cache_policy`:

- `prefer`: return fresh cache when present, else live read.
- `cache_only`: return cache only; error if missing/stale.
- `live`: bypass cache and read xtdata.

The default can be `prefer` because no subscriptions means no cache hit and the
existing live path remains unchanged.

### Optional Minute-Bar Aggregation

Aggregation should happen off the request path. If DB is unavailable, health can
mark the subscription family degraded while hot-cache refresh continues.

## Implementation Phases

1. Pure data structures: hot cache, subscription model/store, backend/period/
   interval/limit validation, refresh planning.
2. Subscription runtime: start/stop with app lifecycle, official
   subscribe/unsubscribe calls, callback normalization, readiness/error tracking.
3. MCP tools: subscribe/unsubscribe/list/status and cache-aware snapshot.
4. Fallback polling: bounded worker calls through existing snapshot logic.
5. Optional DB aggregation: minute OHLCV accumulator and warehouse upsert.
6. qmtctl commands and docs.
7. NAS/manual verification.

## Risks

- Official subscription limits can be broker/entitlement dependent. Mitigate with
  conservative defaults, clear diagnostics, and bounded polling fallback.
- Polling too many codes too often can burden xtdata/QMT. Keep it fallback-only
  by default and expose active backend in health/status output.
- Process-local hot cache disappears on restart. This is acceptable; subscription
  definitions persist and repopulate after startup.
- Mixing cache and live reads can confuse callers. Mitigate by returning explicit
  source/freshness metadata.

## Constitution Check

Passes current project posture:

- read-only;
- opt-in;
- broker-neutral;
- host-testable pure logic;
- graceful degradation;
- no secrets in logs/audit.
