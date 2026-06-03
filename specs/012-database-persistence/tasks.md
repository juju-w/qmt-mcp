# Tasks: Database Persistence (PostgreSQL, optional)

`[x]` = done & verified (incl. real PG round-trip where noted) · `[~]` = needs
amd64/Wine or CI service to fully verify.

## Phase A — Pure logic (host unit tests, no asyncpg)
- [x] T001 `dsn.py`: parse `QMT_DB_URL`, redact password for logs/health.
- [x] T002 `coverage.py`: given cached (min,max) per key + a requested range,
  decide covered / gap (so bars can serve from DB vs. fall back).
- [x] T003 `rows.py`: bars row <-> DB record mappers (broker/code/period/dt/OHLCV).

## Phase B — Engine & migrations (asyncpg; real-PG tested)
- [x] T004 `engine.py` `DbEngine`: background asyncio loop + asyncpg pool; sync
  facade `run(coro, timeout)`; connect/close; redacted diagnostics.
- [x] T005 `migrations.py` + `migrations/0001_init.sql`: `schema_migrations` table
  + `md_bars` warehouse table (PK broker_id, code, period, dividend_type, dt);
  idempotent apply at startup.

## Phase C — Warehouse domain
- [x] T006 `warehouse.py`: `upsert_bars`, `read_bars(range)`, `coverage(key)`
  (ON CONFLICT upsert; broker_id-namespaced).

## Phase D — Config / health / wiring
- [x] T007 `config.py`: `QMT_DB_URL`, `QMT_DB_MARKETDATA` (default on when URL set),
  `QMT_DB_POOL_*`, timeouts.
- [x] T008 `health.py`: `database` state (disabled/connected/degraded/error) +
  db-backed domain list; never flips `ok`.
- [x] T009 `app.py`: build `DbEngine` + run migrations when enabled; inject the
  warehouse into the xtdata bars tool (read-through) and download (write-through);
  graceful fallback to the xtdata path on DB error.
- [x] T010 `docker-compose.yml`: optional `postgres` service behind a `db` profile
  (plain `up` starts no DB); `.env.example` gains `QMT_DB_URL`.

## Phase E — Tests
- [x] T011 unit: `test_db_dsn.py`, `test_db_coverage.py`, `test_db_rows.py` (pure).
- [x] T012 real PG (`@pytest.mark.db`, `QMT_TEST_DB_URL`): migrate → upsert_bars →
  read_bars → coverage round-trip; idempotent re-upsert.

## Phase F — Verify
- [x] T013 Host: ruff + format + unit pytest green; family imports without asyncpg.
- [x] T014 **Real smoke**: `docker run postgres` + venv asyncpg → run migrations +
  warehouse round-trip; tear down. (Done in this environment.)
- [~] T015 amd64/Wine: asyncpg in the image; bars read-through end-to-end with QMT.
- [~] T016 CI: add a `postgres` service container and run the `db` test tier.

## Deferred (next domains; same engine)
- [ ] T017 audit-to-PG sink (002 domain) behind `QMT_DB_AUDIT`.
- [ ] T018 instrument-search cache to PG (006 domain) behind `QMT_DB_INSTRUMENTS`.
