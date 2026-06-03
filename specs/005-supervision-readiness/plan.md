# Implementation Plan: Supervision, Readiness & Autostart

**Branch**: `002-mcp-server-core` (feature pinned via `.specify/feature.json` → `specs/005-supervision-readiness`) | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-supervision-readiness/spec.md`

## Summary

Turn the appliance from "works after a human babysits the RDP session" into a
hands-off, recreate-safe service. Three layers cooperate:

1. **Session/OS layer** — XFCE-autostart (already prototyped in the Dockerfile)
   is hardened into a small **session supervisor** that launches and *restarts*
   the MCP server (and optionally watches the QMT client), survives RDP
   disconnect/reconnect, and runs after `detect-broker` resolves the pack.
2. **MCP Python layer** — the health state stops being static. A background
   **readiness probe** detects QMT login (poll `userdata_mini`/shm + a cheap
   `xtdata` call) and a background **trader connector** (retry/backoff,
   idempotent, reconnect-on-drop) auto-runs `start`+`connect` once QMT is ready.
   Both feed live state into `/healthz` (`xtdata`, `trader`, `accounts`).
3. **Container/orchestration layer** — a Docker `HEALTHCHECK` (and compose
   `healthcheck:`) reflects real MCP state via a lightweight unauthenticated
   liveness probe, plus a **tmpfs startup guard** that refuses/warns when
   `/broker` is on tmpfs (the RAM-exhaustion lesson from 001).

005 builds the trader-connect machinery but can only validate it to the
`not_authorized`/`disabled` boundary locally, because broker programmatic
permission is not yet granted (that is feature [004](../004-account-query-tools/spec.md)'s blocker). The
readiness-detection, connect-attempt, backoff, and graceful-failure paths are
fully testable today.

## Technical Context

**Language/Version**: Windows Python 3.12 inside Wine for the MCP runtime + readiness/connector threads; Bash for the session supervisor, entrypoint, and health/tmpfs guards.

**Primary Dependencies**: existing `qmt_mcp_core` (`health`, `workers`, `config`, `app`); the broker pack's `xtdata`/`xttrader` for readiness probing and the trader handshake; XFCE autostart `.desktop` launchers; the base RDP image's `/usr/bin/entrypoint`. No new third-party packages.

**Storage**: No new persistent storage. Reuses the JSONL audit sink for supervisor/connector lifecycle events; readiness state is in-memory on `HealthState`.

**Testing**: Unit tests for the readiness state machine and connector backoff with a faked `xtdata`/`xttrader` (no Wine needed); Wine-Python smoke for the live readiness probe; shell tests for the tmpfs guard and supervisor restart; a recreate-from-clean manual check for SC-001.

**Target Platform**: Native linux/amd64 Wine appliance container. Apple Silicon emulation-only, not a validation target.

**Project Type**: Containerized local service inside `qmt-wine-rdp/` — additive hardening of 001/002, no new top-level project.

**Performance Goals**: `/healthz` and `/livez` stay responsive (sub-second) regardless of probe/connector activity; readiness is observable within one poll interval of QMT login; MCP restart by the supervisor within a few seconds of crash.

**Constraints**: MCP/QMT need an X session (Wine GUI) so supervision lives **inside** the RDP/XFCE session, not at container PID 1; never block MCP-core startup on QMT readiness (constitution V — serve immediately, gate trader tools); the liveness probe must leak no account/secret detail; fail closed on tmpfs `/broker`.

**Scale/Scope**: One supervisor + one readiness probe + one connector per appliance instance; one broker pack per instance.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Broker-Agnostic Base | Supervisor/probe consume `detect-broker` output; nothing broker-specific baked in; recreate-safe via image, not runtime injection | PASS |
| II. Read-Only by Default | Trader auto-connect establishes the session only; exposes **no** write tools (those stay in a future guarded feature) | PASS |
| III. Reproducible / Native / Pinned | Autostart + supervisor + healthcheck baked into image/compose from the repo; no hand-mutated container state | PASS |
| IV. Contract-First MCP | Health/readiness fields are an explicit, documented contract; `/livez` schema is minimal and typed | PASS |
| V. Observable / Auditable / Readiness-Gated | This feature *is* readiness-gating: live `xtdata`/`trader`/`accounts` state, healthcheck wiring, lifecycle audit | PASS |
| VI. Security by Default | `/livez` is unauthenticated but discloses only liveness (no detail); `/healthz` stays bearer-gated; healthcheck reads token from chmod-600 `mcp.env` | PASS |
| VII. Spec-Driven | 005 scoped to supervision/readiness/autostart; trader *query* tools remain 004; write tools remain future | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/005-supervision-readiness/
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions (supervisor, readiness probe, healthcheck, tmpfs)
├── data-model.md      # readiness state machine + health fields + connector states
├── quickstart.md      # recreate-from-clean validation walkthrough
└── contracts/
    ├── readiness.md   # /healthz live fields + /livez liveness probe contract
    └── supervisor.md  # session supervisor + autostart + tmpfs guard behavior
```

### Source Code (repository root)

```text
qmt-wine-rdp/
├── mcp/
│   └── qmt_mcp_core/
│       ├── health.py        # add live xtdata/trader/accounts + readiness fields
│       ├── readiness.py     # NEW: background readiness probe (QMT-login detect)
│       ├── connector.py     # NEW: background trader connect (retry/backoff, reconnect)
│       └── app.py           # start probe/connector as background tasks; add /livez
├── scripts/
│   ├── qmt-supervisor.sh    # NEW: session supervisor (restart MCP; watch QMT)
│   ├── start-mcp.sh         # launched by supervisor instead of directly by autostart
│   ├── start-qmt.sh         # (optionally) supervised
│   ├── qmt-entrypoint.sh    # add tmpfs guard for /broker before exec entrypoint
│   └── healthcheck.sh       # NEW: container HEALTHCHECK → /livez (or /healthz w/ token)
├── Dockerfile               # autostart calls supervisor; add HEALTHCHECK; bake supervisor
└── docker-compose.yml       # add healthcheck:; document tmpfs/real-disk requirement
```

**Structure Decision**: Keep everything inside `qmt-wine-rdp/`, additive to
001/002. The supervisor is a small Bash loop launched by the existing XFCE
autostart (not a container-level init), because MCP/QMT require the X session.
Readiness and connector logic live as background threads in `qmt_mcp_core` so a
single process owns health truth; they reuse `WorkerPool` semantics for the
blocking SDK calls rather than introducing a new concurrency model.

## Complexity Tracking

> Not required — Constitution Check passed with no violations.

The one notable tension (supervision is session-scoped, but a Docker healthcheck
wants a session-independent signal) is resolved in [research.md](./research.md)
without adding a second init system: the healthcheck targets the MCP HTTP
liveness endpoint, which is up exactly when the session-supervised MCP is up.
