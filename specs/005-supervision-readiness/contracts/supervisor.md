# Contract: Session Supervisor, Autostart & Startup Guards

Covers the OS/session-layer behavior: how MCP/QMT start, get restarted, survive
RDP churn, and how unsafe storage is refused.

## Autostart (baked into the image — recreate-safe)

- XFCE autostart `.desktop` entries launch the **supervisor** on RDP login (the
  existing `qmt-mcp.desktop` is repointed from `start-mcp.sh` to
  `qmt-supervisor.sh`; `qmt-client.desktop` continues to launch the QMT client,
  optionally under supervision).
- Autostart MUST be present in the image (no runtime injection); a fresh
  `docker compose up` of a recreated container reproduces it (constitution III).
- Ordering: `qmt-entrypoint.sh` runs `detect-broker` and writes `/run/qmt/broker.env`
  + `/opt/qmt-mcp/mcp.env` **before** the session starts, so the supervisor always
  sees resolved config.

## Supervisor (`qmt-supervisor.sh`)

- Runs inside the XFCE session (needs `DISPLAY`).
- Launches `start-mcp.sh` as a child; on child exit, **restarts** it with capped
  exponential backoff (`QMT_SUPERVISOR_BACKOFF_MAX_S`, default 60s).
- Appends lifecycle records to the audit sink (`supervisor.start`,
  `supervisor.restart` with `exit_code`/`attempt`/`backoff_s`). No secrets.
- The QMT client is launched once; a crashed QMT login needs a human (login is
  manual), so QMT is watched/logged but not aggressively restarted.
- Idempotent: a second autostart firing MUST NOT spawn duplicate MCP processes
  (single-instance guard, e.g. pidfile/port check).

Invariants:
- MUST NOT be the container PID 1 (MCP/QMT need the post-login X session).
- A killed MCP process is replaced within a few seconds (SC-003).

## RDP disconnect/reconnect (FR-006)

- The supervisor + MCP + QMT are scoped to the **XFCE session**, not the RDP
  connection. Disconnecting/reconnecting the RDP client MUST NOT tear down the
  MCP. If the base image binds session lifetime to the connection, the image
  config pins the session to persist. Verified by a disconnect→reconnect check.

## tmpfs startup guard (FR-007)

- At the top of `qmt-entrypoint.sh`, before resolving the pack and before
  `exec /usr/bin/entrypoint`:
  - Determine the fs type backing `BROKER_MOUNT` (default `/broker`) via
    `stat -f -c %T` / `/proc/mounts`.
  - If `tmpfs`/`ramfs`:
    - default (`QMT_ALLOW_TMPFS_BROKER` unset/`0`): **exit non-zero** with a
      clear message ("`/broker` is on tmpfs — the broker pack/userdata must live
      on real disk; set QMT_ALLOW_TMPFS_BROKER=1 to override").
    - `QMT_ALLOW_TMPFS_BROKER=1`: emit a loud warning and continue.
- Fail closed (constitution Security & Safety) — prevents the 001 RAM-exhaustion
  crash before any heavy Wine startup.

## Docker healthcheck wiring (FR-005)

- `Dockerfile` `HEALTHCHECK` runs `healthcheck.sh`, which probes `/livez` on
  `localhost:${MCP_PORT}` and exits non-zero on failure.
- `docker-compose.yml` adds a matching `healthcheck:` block (interval/timeout/
  retries/start_period sized so QMT-login latency doesn't mark the container
  unhealthy — liveness is MCP-serving, independent of QMT login).
- The healthcheck uses NO bearer token (it targets unauthenticated `/livez`).

## Acceptance mapping

| Spec criterion | Contract check |
|---|---|
| SC-001 clean recreate → both running, zero manual steps | autostart+supervisor baked, detect-broker first |
| SC-003 kill MCP → auto-restart in N s | supervisor restart loop + backoff |
| SC-004 healthcheck reflects up/down | `HEALTHCHECK`→`/livez` |
| FR-007 tmpfs guard | entrypoint fails closed on tmpfs `/broker` |
| FR-006 RDP churn safe | session-scoped processes survive reconnect |
