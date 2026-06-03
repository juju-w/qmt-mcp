# 012 Verification

Date: 2026-06-04 · Host: darwin/arm64, Python 3.12.2. **The DB layer is pure
Python (not Wine-bound), so it was tested for real against a PostgreSQL 16
container here** — unlike Wine/xttrader features, this is genuine end-to-end
validation.

## Real-PostgreSQL test (executed)

`docker run postgres:16` + a venv with `asyncpg 0.31.0`, DSN
`postgresql://postgres:***@127.0.0.1:55432/qmt`:

- DSN parse + redact (password masked) ✅
- `DbEngine.connect()` via the background-loop sync facade ✅
- `apply_migrations` applied `0001_init.sql`; **idempotent** re-run = `[]` ✅
- `Warehouse.upsert_bars` 3 rows; `coverage` → `{min:20250101, max:20250103, count:3}` ✅
- `is_covered` true for in-range, false for over-range ✅
- `read_bars` range query returns ordered rows ✅
- **idempotent re-upsert**: count stays 3, `close` updated via `ON CONFLICT` (99.9) ✅
- run as a pytest `@pytest.mark.db` test against the live container: **1 passed** ✅

## Host results

| Check | Command | Result |
|---|---|---|
| Unit tests | `pytest -m 'not integration'` | ✅ 109 passed (incl. db dsn/coverage/rows: 16) |
| DB tier gating | `pytest` with no asyncpg | ✅ db tier skips cleanly (importorskip) |
| DB tier live | `QMT_TEST_DB_URL=... pytest -m db` (venv+container) | ✅ 1 passed |
| Lint / format | `ruff check` / `ruff format --check` | ✅ clean |
| Compose | `yaml.safe_load` (default + tls) | ✅ valid |
| Entrypoint | `bash -n` | ✅ ok |

## Implemented

- `qmt_mcp_db/`: `dsn` (parse+redact), `coverage` (range math), `rows` (mappers) —
  all pure/host-tested; `engine` (asyncpg pool + background-loop sync facade,
  lazy import), `migrations` (numbered SQL + `schema_migrations`), `warehouse`
  (bars upsert/read/coverage, broker_id-namespaced).
- Wiring: `config` (`QMT_DB_URL`/`QMT_DB_MARKETDATA`/`QMT_DB_POOL_MAX`),
  `health.database` + `db_domains`, `app._make_warehouse` (fail-safe: DB init
  error → `database=error`, returns None, appliance keeps working), bars tool
  **read-through/write-through** for single-code closed ranges with graceful
  fallback (`database=degraded`) on any DB error.
- Ops: optional `db` (postgres:16) compose service behind a **profile** (plain
  `up` starts no DB); `.env.example` + entrypoint bridge; `asyncpg` declared in
  `requirements.in` and the Dockerfile pip line.

## Needs amd64 / live validation

- `asyncpg` installing in the **Wine** Windows-Python image (added to the pip line;
  amd64 build only).
- bars **read-through end-to-end with live xtdata** (warehouse fill on miss → serve
  from DB on hit) — needs QMT logged in.
- CI: add a `postgres` service container + run `pytest -m db` (T016).
