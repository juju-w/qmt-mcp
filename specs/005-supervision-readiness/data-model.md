# Phase 1 Data Model: Supervision, Readiness & Autostart

No persistent storage is introduced. The "entities" here are in-memory state on
the MCP process plus the lifecycle records appended to the existing audit sink.

## 1. Readiness state machine (in `readiness.py`, surfaced on `HealthState`)

States for QMT-login / xtdata readiness:

| State | Meaning | Entry condition |
|---|---|---|
| `starting` | Probe not yet run | process boot |
| `awaiting_login` | MCP up, QMT not logged in | filesystem/SDK signals absent |
| `ready` | xtdata usable | filesystem signal present **and** SDK probe ok |
| `degraded` | Was ready, probe now failing | SDK probe fails after being `ready` |

Transitions (poll interval, default 5s):

```text
starting ──► awaiting_login ──(fs ok + sdk ok)──► ready
awaiting_login ◄──(signals lost)── ready
ready ──(sdk probe fails)──► degraded ──(sdk ok)──► ready
```

Fields added/derived:
- `xtdata`: `disabled` | `awaiting_login` | `ready` | `degraded` | `error`
  (replaces today's static `disabled`/`error` with live values when enabled)
- `readiness.qmt_login`: `unknown` | `awaiting` | `logged_in`
- `readiness.last_probe_at`: ISO timestamp
- `readiness.last_error`: short reason string (no secrets)

## 2. Trader connector state (in `connector.py`, surfaced as `HealthState.xttrade`)

| State | Meaning |
|---|---|
| `disabled` | Connector off by config (default until 004/permission) |
| `not_authorized` | `connect()` rejected — broker permission not granted |
| `trader-not-ready` | QMT not logged in yet / handshake not attempted |
| `connecting` | Handshake in progress (within backoff window) |
| `connected` | Session established, idempotent reconnect armed |
| `error` | Unexpected failure (non-auth); retried with backoff |

Backoff parameters (config, with defaults):
- `QMT_CONNECT_RETRY` (existing, default 8) — max attempts before sustained
  `trader-not-ready`/`error` reporting (still keeps retrying on a long interval)
- base delay 2s, exponential, capped (e.g. 60s); idempotent: a successful
  `connected` short-circuits further attempts until a drop is detected.

Reconnect: on detecting a dropped session, re-enter `connecting` and re-run the
handshake; never exposes write tools.

## 3. Health document (extends 002 `/healthz`)

Existing fields (`server`, `transport`, `broker_config`, `xtquant_import`,
`xtdata`, `xttrade`, `audit`, `tool_families`) are retained. 005 makes
`xtdata`/`xttrade` **live** and adds a structured `readiness` object:

```json
{
  "ok": true,
  "server": "live",
  "xtdata": "ready",
  "xttrade": "not_authorized",
  "readiness": {
    "qmt_login": "logged_in",
    "xtdata_state": "ready",
    "trader_state": "not_authorized",
    "last_probe_at": "2026-06-04T08:00:00Z",
    "last_error": ""
  },
  "tool_families": [ ... ]
}
```

`ok` semantics (unchanged trigger set, documented): `ok=true` when the server is
serving and audit is healthy. Readiness states do **not** flip `ok` to false —
they are reported, not fatal (the MCP is intentionally up before QMT login).

## 4. Liveness document (new `/livez`, unauthenticated)

Minimal, secret-free:

```json
{ "ok": true, "server": "live" }
```

Returns HTTP 200 with `ok:true` while the app is serving; the absence of a
response (connection refused / process down) is itself the unhealthy signal for
the Docker healthcheck.

## 5. Supervisor lifecycle records (audit sink, reused)

Append-only JSONL events (no secrets), e.g.:
- `supervisor.start` (child=`mcp`, pid)
- `supervisor.restart` (child=`mcp`, exit_code, attempt, backoff_s)
- `connector.attempt` / `connector.connected` / `connector.not_authorized`
- `readiness.transition` (from, to)

These reuse the existing `JsonlAuditSink`; the supervisor (Bash) appends via a
small structured line, the Python threads via the existing sink.

## 6. Environment / config knobs (additive to `config.py`)

| Var | Default | Purpose |
|---|---|---|
| `QMT_READINESS_POLL_S` | `5` | readiness probe interval |
| `QMT_ENABLE_CONNECTOR` | `0` | enable background trader connect (off until 004/permission) |
| `QMT_CONNECT_RETRY` | `8` (existing) | connector attempt budget |
| `QMT_ALLOW_TMPFS_BROKER` | `0` | escape hatch for the tmpfs guard |
| `QMT_SUPERVISOR_BACKOFF_MAX_S` | `60` | cap on MCP restart backoff |

All fail closed: connector defaults off; tmpfs guard defaults to block.
