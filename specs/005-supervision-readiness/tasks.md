# Tasks: Supervision, Readiness & Autostart

> Backfilled after implementation (005 was built directly from plan + contracts +
> data-model; this records the work and its verification state). `[x]` = done &
> host-verified · `[~]` = implemented, needs amd64/live validation (see VERIFICATION).

## Phase A — Config & health surfaces
- [x] T001 `config.py`: add `QMT_READINESS_POLL_S`, `QMT_ENABLE_CONNECTOR`
  (default off), `QMT_CONNECT_RETRY`, `QMT_CONNECT_BACKOFF_MAX_S` (with defaults).
- [x] T002 `health.py`: live `qmt_login` + `readiness()` object on `/healthz`;
  `livez()` (minimal, secret-free); readiness states never flip `ok`.

## Phase B — Readiness probe
- [x] T003 `readiness.py` `ReadinessProbe`: fs + sdk signals → state machine
  (`awaiting_login`/`ready`/`degraded`), injectable callables, `step()` seam, daemon `run()`.

## Phase C — Trader connector
- [x] T004 `connector.py` `TraderConnector`: idempotent connect, capped exp backoff,
  reconnect-on-drop, `not_authorized` mapping, `attempt()` seam. Off by default.

## Phase D — App wiring
- [x] T005 `app.py`: unauthenticated `/livez` handled **before** the auth gate.
- [x] T006 `app.py`: build probe/connector in `create_app`; start in `main()`
  (connector only when `QMT_ENABLE_CONNECTOR=1`); real fs/sdk + connect scaffolds.

## Phase E — Tests (host, no Wine)
- [x] T007 `test_readiness.py` — 6 cases (awaiting/ready/degraded/recover/login-lost/exception).
- [x] T008 `test_connector.py` — 7 cases (not-ready/connect/not_authorized/error/idempotent/reconnect/backoff).
- [x] T009 `test_health.py` + `test_config.py` — readiness/livez fields + new knobs.
- [x] T010 integration: `/livez` shape + `/healthz` readiness object (gated on fastmcp).

## Phase F — Session/OS scripts
- [x] T011 `qmt-supervisor.sh` — restart MCP w/ capped backoff + single-instance guard (`bash -n`).
- [x] T012 `healthcheck.sh` — probe `/livez` (`bash -n`).
- [x] T013 `qmt-entrypoint.sh` — tmpfs guard (warn-by-default; `QMT_ENFORCE_REALDISK=1`
  enforces) + bridge new env into `mcp.env` (`bash -n`).

## Phase G — Image / compose
- [~] T014 `Dockerfile`: autostart launches the supervisor; add `HEALTHCHECK` → `/livez`.
- [x] T015 `docker-compose.yml`: visible `healthcheck:` block (YAML validated).

## Phase H — Verification
- [x] T016 Host: ruff + ruff format + `pytest` (71 passed); scripts `bash -n`; compose YAML.
- [~] T017 amd64 quickstart: recreate→login→autostart; readiness flip; supervisor
  restart; healthcheck transitions; tmpfs guard; RDP reconnect; connector path.
  (See `quickstart.md` / `VERIFICATION.md` — requires a native amd64 host + broker pack.)
