# Implementation Plan: Database Persistence (PostgreSQL, optional)

**Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

## Summary

A new optional `qmt_mcp_db` package providing a **native-async** PostgreSQL layer
(driver: **asyncpg**) behind a **sync facade** so the existing sync tool/worker
model is unchanged. Off by default; enabled by `QMT_DB_URL`. First domain: the
**market-data warehouse** (bars/history) with write-through on download and
read-through on `qmt_xtdata_bars`. Graceful degradation to the file/xtdata path on
DB outage. Pure-logic parts are host-unit-tested; the live DB path is tested for
real against a Postgres container here (docker available) and in CI via a
`postgres` service container.

## Technical Context

**Language/Version**: Python 3.12. **Driver**: `asyncpg` (native async). Optional
dependency — only needed when the DB is enabled.

**Concurrency bridge**: `DbEngine` owns a dedicated asyncio loop in a daemon thread
and an `asyncpg` pool; a sync facade `run(coro, timeout)` submits via
`run_coroutine_threadsafe`. This keeps async DB I/O off the request/event loop
while the sync tool layer (registry + WorkerPool) calls it like any blocking dep.

**Migrations**: numbered `.sql` files + a `schema_migrations` table, applied
idempotently at startup. No ORM.

**Testing**: host unit tests for DSN parse/redact, coverage math, row mappers (no
asyncpg needed); a `@pytest.mark.db` tier that runs migrations + warehouse
round-trip against a real PG (`QMT_TEST_DB_URL`), skipped when unset.

**Constraints**: opt-in (no DB → unchanged); fail-safe fallback; never block the
loop; DSN/password redacted everywhere; `broker_id`-namespaced; bounded writes.

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| I. Broker-Agnostic | DB optional + `broker_id`-namespaced; nothing broker-specific baked | PASS |
| II. Read-Only by Default | warehouse stores market data only; no trade writes | PASS |
| III. Reproducible | versioned migrations from repo; pinned optional dep | PASS |
| IV. Contract-First | health `database` state; structured rows (no raw passthrough) | PASS |
| V. Observable / Auditable | health surfaces db + domains; graceful degrade reported | PASS |
| VI. Security | DSN only in `.env`; redacted in logs/health; no secrets committed | PASS |
| VII. Spec-Driven | scoped to PG marketdata warehouse first; audit/cache domains staged | PASS |

## Project Structure

```text
appliance/mcp/
├── qmt_mcp_db/
│   ├── __init__.py
│   ├── dsn.py           # parse + redact DSN (pure, host-tested)
│   ├── coverage.py      # cached-range coverage math (pure, host-tested)
│   ├── rows.py          # bars <-> DB row mappers (pure, host-tested)
│   ├── engine.py        # asyncpg pool + background-loop sync facade (asyncpg)
│   ├── migrations.py    # numbered-migration runner
│   ├── migrations/0001_init.sql ...
│   └── warehouse.py     # bars upsert / read / coverage (uses engine)
└── qmt_mcp_core/
    ├── config.py        # QMT_DB_URL, QMT_DB_MARKETDATA, pool size, timeouts
    ├── health.py        # `database` state + db-backed domains
    └── app.py           # build DbEngine when enabled; pass warehouse to xtdata bars
appliance/docker-compose.yml   # optional `db` (postgres) service behind a profile
```

**Structure Decision**: Mirror the xtdata/xttrade package layout. Pure modules
(dsn/coverage/rows) carry the unit-tested logic; `engine.py` is the only asyncpg
touchpoint (lazy import) so the rest imports without the driver. The xtdata bars
tool gains an optional warehouse hook; with no DB it behaves exactly as today.

## Complexity Tracking

> Not required — Constitution Check passed. The async-bridge (background loop) is
> the one non-trivial piece; justified by honoring native-async asyncpg while
> keeping the proven sync tool/worker model unchanged.
