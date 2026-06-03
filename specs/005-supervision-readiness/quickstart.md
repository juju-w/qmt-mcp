# Quickstart: Validating Supervision, Readiness & Autostart

Validates the 005 acceptance criteria. Runs against the appliance container on a
native linux/amd64 host with a mounted broker pack. Steps that need broker
**programmatic permission** are marked — without it, only the
`not_authorized`/`disabled` boundary is observable (the [004](../004-account-query-tools/spec.md) blocker).

## 0. Prerequisites

- `qmt-wine-rdp/.env` set (`QMT_MCP_TOKEN`, `BROKER_PACK`, ports).
- Broker pack on **real disk** (not tmpfs).

## 1. tmpfs guard fails closed (FR-007 / SC: safety)

```bash
# Point BROKER_PACK at a tmpfs path (e.g. a RAM dir) and start:
docker compose up                      # expect: non-zero exit, clear tmpfs message
QMT_ALLOW_TMPFS_BROKER=1 docker compose up   # expect: loud warning, continues
```

Expected: default run refuses with a `/broker is on tmpfs ...` message; the
override downgrades to a warning.

## 2. One-login startup, recreate-safe (US1 / SC-001)

```bash
docker compose down && docker compose up -d   # clean recreate
# RDP into localhost:${RDP_PORT:-13389} as wineuser
```

Expected after RDP login, with **zero manual steps**:
- QMT terminal window appears (autostart).
- MCP is serving: `curl -fsS localhost:${MCP_PORT:-18765}/livez` → `{"ok":true,...}`.

## 3. Liveness vs. authed health (FR-005, Principle VI)

```bash
# Liveness — no token, opaque:
curl -fsS localhost:${MCP_PORT:-18765}/livez
# -> {"ok": true, "server": "live"}

# Detailed health — requires token:
curl -s localhost:${MCP_PORT:-18765}/healthz                       # -> 401
curl -s -H "Authorization: Bearer $QMT_MCP_TOKEN" \
     localhost:${MCP_PORT:-18765}/healthz | jq .readiness
```

Expected before QMT login: `readiness.qmt_login: "awaiting"`, `xtdata:
"awaiting_login"`, `xttrade: "not_authorized"`, but top-level `ok: true`.

## 4. Readiness flips after QMT login (US1.2 / FR-002)

Log into QMT 独立交易 over RDP, then within one poll interval (~5s):

```bash
curl -s -H "Authorization: Bearer $QMT_MCP_TOKEN" \
     localhost:${MCP_PORT:-18765}/healthz | jq '{xtdata, xttrade, readiness}'
```

Expected: `readiness.qmt_login: "logged_in"`, `xtdata: "ready"`.

- **With broker permission** (deferred): `xttrade` progresses `connecting` →
  `connected` automatically (no manual init/start/connect).
- **Without permission** (current reality): `xttrade: "not_authorized"`, server
  stays `ok` — clear diagnosis, not a broken server.

## 5. Self-healing: kill MCP, expect restart (US2.1 / SC-003)

```bash
# In a desktop terminal or via docker exec, find and kill the MCP python:
pkill -f qmt_mcp.py
# Within a few seconds:
curl -fsS localhost:${MCP_PORT:-18765}/livez   # -> back to {"ok":true,...}
```

Expected: supervisor restarts MCP; `/livez` recovers; an audit
`supervisor.restart` record is written.

## 6. Docker healthcheck reflects state (US2.2 / SC-004)

```bash
docker inspect --format '{{.State.Health.Status}}' qmt-default   # -> healthy
pkill -f qmt_mcp.py    # briefly, before supervisor restarts
docker inspect --format '{{.State.Health.Status}}' qmt-default   # transient unhealthy → healthy
```

## 7. RDP disconnect/reconnect does not wedge MCP (FR-006)

Disconnect the RDP client, reconnect after a minute:

```bash
curl -fsS localhost:${MCP_PORT:-18765}/livez   # -> still {"ok":true,...} throughout
```

Expected: MCP serves continuously across the RDP churn.

## Unit/offline checks (no Wine/QMT needed, CI-friendly)

- Readiness state machine transitions (`starting`→`awaiting_login`→`ready`→
  `degraded`→`ready`) with a fake `xtdata`.
- Connector backoff/idempotency/reconnect and `not_authorized` mapping with a
  fake `xttrader`.
- tmpfs guard shell logic (mock `stat -f` output).
- `/livez` returns only `{ok, server}`; `/healthz` still 401 without token.
