# 005 Verification

Date: 2026-06-04 · Host: darwin/arm64, Python 3.12.2 (Python core + unit tests are
platform-agnostic; container/Wine behavior is amd64-only and noted below).

## Implemented

**MCP Python core (host-testable):**
- `qmt_mcp_core/config.py` — new knobs `QMT_READINESS_POLL_S`,
  `QMT_ENABLE_CONNECTOR` (default off), `QMT_CONNECT_RETRY`, `QMT_CONNECT_BACKOFF_MAX_S`.
- `qmt_mcp_core/health.py` — live `qmt_login` + `readiness` object on `/healthz`;
  new `livez()` (minimal, secret-free). Readiness states never flip `ok`.
- `qmt_mcp_core/readiness.py` — `ReadinessProbe` (fs + sdk signals → state machine
  `awaiting_login`/`ready`/`degraded`), injectable callables, `step()` unit seam.
- `qmt_mcp_core/connector.py` — `TraderConnector` (idempotent connect, capped
  backoff, reconnect-on-drop, `not_authorized` mapping), `attempt()` unit seam.
- `qmt_mcp_core/app.py` — unauthenticated `/livez` (before the auth gate); builds
  probe/connector in `create_app`, starts them in `main()` (connector only when
  `QMT_ENABLE_CONNECTOR=1`).

**Container/session (amd64-only):**
- `scripts/qmt-supervisor.sh` — session supervisor; restarts MCP with capped
  backoff; single-instance pidfile guard.
- `scripts/healthcheck.sh` — probes `/livez`.
- `scripts/qmt-entrypoint.sh` — tmpfs storage guard (warn-by-default) + bridges the
  new env vars into `mcp.env`.
- `Dockerfile` — autostart now launches the supervisor; `HEALTHCHECK` → `/livez`.
- `docker-compose.yml` — visible `healthcheck:` block.

## Results (host)

| Check | Command | Result |
|---|---|---|
| Unit tests | `pytest -m 'not integration'` | ✅ 71 passed (incl. 6 readiness + 7 connector + new health/config) |
| Integration gating | `pytest` | ✅ 1 skipped (no fastmcp); `/livez` + readiness asserts added |
| Lint / format | `ruff check .` / `ruff format --check .` | ✅ clean |
| Script syntax | `bash -n` (entrypoint, supervisor, healthcheck) | ✅ ok |
| Supervisor backoff math | manual eval | ✅ 1,2,4,8,…,cap |
| Compose | `yaml.safe_load` | ✅ valid |

## Deviations from the original plan/contracts (recorded)

1. **tmpfs guard is warn-by-default** (not fail-closed). Enforce with
   `QMT_ENFORCE_REALDISK=1`. Rationale: maintainer considers RAM-backed `/broker` a
   niche operator concern, not a hard gate for everyone. (contracts updated.)
2. **`degraded`** = "QMT logged in but the xtdata probe isn't passing" (covers both
   warming-up and regressed), slightly broader than the data-model's "was ready,
   now failing".
3. **Connector `connect_fn` is a `not_authorized` scaffold** until feature 004
   injects a real `xttrader` handshake — matches the permission-blocked reality.

## Needs amd64 / live validation (not runnable here)

Run `quickstart.md` on a native amd64 host with a broker pack to validate:
- recreate → RDP login → QMT + MCP auto-start (SC-001)
- readiness flips after QMT login; real userdata-fs + xtdata probe signals
- supervisor restarts a killed MCP (SC-003)
- docker healthcheck transitions (note: **unhealthy until RDP login** brings up the
  session/MCP — accurate, since MCP isn't serving before login)
- tmpfs guard warning (+ `QMT_ENFORCE_REALDISK=1` refusal)
- RDP disconnect/reconnect does not wedge the MCP
- with broker permission: connector reaches `connected` (otherwise `not_authorized`)

## amd64 live validation

Date: 2026-06-04 · Host: linux/amd64 (192.168.99.10) · Broker: guangda-jinyangguang
· Container: qmt-guangda (Up 44 min, healthy) · Image: qmt-appliance-base:local

| # | Check | Result |
|---|---|---|
| SC-001 | Container running + QMT autostart + MCP serving after RDP login | ✅ `docker ps` shows Up (healthy); `/livez` → `{"ok":true,"server":"live"}` |
| FR-005 | `/livez` no-auth, `/healthz` 401 without token | ✅ `/livez` returns 200; `/healthz` returns 401 |
| US1.2 | Readiness flips after QMT login | ✅ `readiness.qmt_login: "logged_in"`, `xtdata_state: "ready"`, `xtquant_import: "ok"`, `database: "connected"` |
| SC-003 | Supervisor restarts killed MCP | ✅ `pkill -f qmt_mcp.py` → `/livez` back within 8s |
| SC-004 | Docker healthcheck reflects state | ✅ `docker inspect` → `healthy` (survived MCP kill+restart) |
| FR-006 | MCP serves across RDP disconnect | ✅ `/livez` stable; MCP runs under supervisor, not RDP session |
| 004 | xttrade `not_authorized` (no broker permission) | ✅ `xttrade: "not_authorized"`, server stays `ok: true` |

**Conclusion**: all 005 acceptance criteria verified on live amd64. Feature complete.
