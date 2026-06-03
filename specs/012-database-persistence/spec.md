# Feature Specification: Database Persistence (PostgreSQL, optional)

**Status**: Draft
**Depends on**: 002 (audit sink + health + error envelopes), 003 (market-data/bars),
006 (instrument-search cache). Realizes the persistence feature 002 deferred
("optional Postgres audit/query store, market-data warehousing").

## Summary

Add an **optional**, configurable PostgreSQL persistence layer so large/long-lived
data is not stuck on the appliance's local disk. The motivating problem: historical
market data (downloaded via `download_history`) and the instrument-search cache can
grow too large to keep comfortably on the local box; persisting them in a database
lets one DB serve many appliance instances and survive container recreation.

Persistence is **off by default** — the appliance keeps working exactly as today
with file/JSONL stores when no database is configured (no mandatory DB; preserves
the broker-agnostic, fail-closed posture from the constitution). When enabled, the
operator can either point at an **existing/external PostgreSQL** or let
**docker-compose start a bundled PostgreSQL** service. Reads are served from the DB
when present (local cache → DB write-through); a DB outage degrades gracefully back
to the file defaults and is reported in health.

## User Scenarios

### US1 — No database (default, unchanged) (P1)
**Acceptance**: With no DB configured, the appliance behaves exactly as before —
JSONL audit, file/QMT-local market-data cache, JSON instrument-search cache. Health
reports `database: disabled`. Nothing requires Postgres.

### US2 — Use an existing external PostgreSQL (P1)
**Acceptance**: Given `QMT_DB_URL` points at a reachable PostgreSQL, when the MCP
starts, then it connects, applies schema migrations, and enabled persistence
domains read/write the DB. Health reports `database: connected`.

### US3 — Bundled database via docker-compose (P1)
**Acceptance**: Given the operator runs compose with the `db` profile, a
PostgreSQL service starts, the MCP waits for it, and persistence works with no
external DB. Default `docker compose up` (no profile) does **not** start a DB.

### US4 — Warehouse large market data (P1, the motivating case)
**Acceptance**: When historical bars are downloaded, they are upserted into a
DB table (namespaced by broker/market/code/period). Subsequent `qmt_xtdata_bars`
reads for a cached range are served from the DB without re-downloading, so the
local box is not overwhelmed.

### US5 — Graceful degradation (P2)
**Acceptance**: If the DB becomes unreachable at runtime, persistence-backed reads
fall back to the file/QMT-local path (or return a clear `persistence`/`dependency`
error for DB-only operations), health flips to `database: degraded`, and the MCP
stays up. Audit guarantees remain explicit (per 002).

## Functional Requirements

- **FR-001**: Persistence MUST be **opt-in**. With no DB config, behavior is
  identical to today (file/JSONL). An empty/invalid DB config yields the file
  default (fail-safe), never a hard startup failure unless the operator explicitly
  requires the DB.
- **FR-002**: Two connection modes: (a) external PostgreSQL via a DSN
  (`QMT_DB_URL`, secret — `.env` only, never committed); (b) a compose-managed
  `db` service behind a compose **profile** so default `up` stays DB-free.
- **FR-003**: Independently toggleable persistence **domains**:
  (a) **market-data warehouse** (bars/history) — primary;
  (b) **instrument-search cache** (006);
  (c) **audit log** (002, currently JSONL) — optional DB sink.
- **FR-004**: Schema is created/upgraded by **versioned migrations** at startup;
  idempotent **upserts**; data namespaced by `broker_id` (multi-instance safe).
- **FR-005**: Market-data write-through/read-through: download tools persist rows;
  bars reads serve cached ranges from the DB to avoid re-download and local-disk
  pressure. Range/coverage tracking so partial caches are detectable.
- **FR-006**: Runtime DB outage degrades gracefully (fall back to file default or
  a clear error for DB-only ops); MUST NOT crash the server. Health surfaces
  `database` state (`disabled` | `connected` | `degraded` | `error`) and which
  domains are DB-backed.
- **FR-007**: Connection pooling + bounded writes (reuse the worker model); never
  block the event loop or the request path on DB I/O.
- **FR-008**: Secrets: DB credentials only in `.env`/runtime, never in images, git,
  logs, audit, or `broker.yaml`. The DSN is redacted in any diagnostic output.
- **FR-009**: A migration/health/bootstrap path that is reproducible from the repo
  (no hand-mutated DB); documented backup/retention guidance.

## Success Criteria

- **SC-001**: With no DB config, the full existing test suite + behavior is
  unchanged; health shows `database: disabled`.
- **SC-002**: With `QMT_DB_URL` set to a reachable PG, migrations apply and a
  `download_history` run results in queryable rows; a subsequent bars read for that
  range is served from the DB (no re-download).
- **SC-003**: `docker compose --profile db up` starts PG and the MCP uses it;
  plain `docker compose up` starts no DB.
- **SC-004**: Stopping the DB at runtime flips health to `degraded` and the MCP
  keeps serving (file fallback / clear errors), no crash.
- **SC-005**: DSN/password never appears in logs, audit, or health output.

## Out of Scope / Deferred

- Analytics/BI, OLAP, or a full data-warehouse query API.
- Time-series engines (TimescaleDB/ClickHouse) — PG only here; may follow.
- Streaming/real-time tick capture into the DB.
- Cross-instance coordination beyond `broker_id` namespacing.

## Assumptions / Dependencies

- PostgreSQL (a widely available, free, well-supported relational DB).
- The DB layer is a new optional package alongside `qmt_mcp_core`; pure-logic parts
  (DSN parsing/redaction, coverage math, row mappers) are host-unit-testable; live
  DB paths are validated against a real/compose PG (CI may use a `postgres` service
  container).
- Honors 002's posture: JSONL/file remains the default; DB is an additive adapter.
