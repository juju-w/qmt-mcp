# Contract: Readiness & Liveness Surfaces

Extends the 002 health contract ([../../002-mcp-server-core/contracts/health.md](../../002-mcp-server-core/contracts/health.md)).
Two HTTP surfaces; both served by `CoreASGI` before the FastMCP app.

## `GET /livez` — unauthenticated liveness (NEW)

- **Auth**: none. This is the only unauthenticated surface; it MUST disclose no
  account, broker, token, path, or readiness detail.
- **200 body**: `{ "ok": true, "server": "live" }`
- **Unhealthy**: process down / app wedged ⇒ connection refused or non-200.
- **Consumers**: Docker `HEALTHCHECK`, compose `healthcheck:`, external LB pings.

Invariants:
- MUST NOT require a bearer token (orchestration has no credential).
- MUST NOT include any field beyond `ok` and `server`.
- `ok:true` ⇔ the uvicorn app is serving requests.

## `GET /healthz` — authenticated, detailed (EXTENDED)

- **Auth**: bearer token required (unchanged from 002).
- Existing fields retained: `server`, `transport`, `broker_config`,
  `xtquant_import`, `xtdata`, `xttrade`, `audit`, `tool_families`.
- **`xtdata`** becomes live: `disabled` | `awaiting_login` | `ready` |
  `degraded` | `error`.
- **`xttrade`** becomes live: `disabled` | `not_authorized` | `trader-not-ready`
  | `connecting` | `connected` | `error`.
- **NEW `readiness` object**:

  | Field | Type | Values |
  |---|---|---|
  | `qmt_login` | string | `unknown` \| `awaiting` \| `logged_in` |
  | `xtdata_state` | string | mirrors `xtdata` |
  | `trader_state` | string | mirrors `xttrade` |
  | `last_probe_at` | string (ISO) | last readiness poll time |
  | `last_error` | string | short reason, **no secrets/paths-with-creds** |

Invariants:
- `ok` is NOT flipped false by `awaiting_login`/`not_authorized`/`trader-not-ready`
  — these are reported states, not server faults (the MCP serves before QMT login,
  per constitution V).
- `ok` is flipped false only on `server`/`audit` faults (unchanged from 002).
- `last_error` is sanitized: no token, no full credential paths.

## Readiness probe behavior

- Runs as a background task started in `create_app`/`main`; MUST NOT block
  startup or the request path.
- Poll interval `QMT_READINESS_POLL_S` (default 5s).
- `ready` requires BOTH: QMT `userdata_mini` filesystem signal present AND a cheap
  `xtdata` probe succeeding through `WorkerPool` with a short timeout.
- A failing probe after `ready` ⇒ `degraded` (not `error`), recovers to `ready`.

## Trader connector behavior

- Disabled by default (`QMT_ENABLE_CONNECTOR=0`); when enabled, attempts the
  `xttrader` handshake only after readiness reports `logged_in`.
- Idempotent (no-op when `connected`); reconnects on drop.
- Authorization failure ⇒ `xttrade: not_authorized`, server stays `ok`.
- Exposes NO write/trade tools (constitution II).

## Acceptance mapping

| Spec criterion | Contract check |
|---|---|
| US1.2 trader auto-connect, `/healthz` ready | connector reaches `connected` after `logged_in` (permissioned) |
| US2.2 healthcheck up/down | `/livez` 200 ⇔ serving; refused ⇔ down |
| US2.3 distinguish states | `readiness.qmt_login` / `xtdata_state` / `trader_state` distinct |
| FR-008 (004) unpermissioned clarity | `xttrade: not_authorized`, `ok:true` |
