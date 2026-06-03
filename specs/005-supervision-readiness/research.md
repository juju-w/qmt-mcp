# Phase 0 Research: Supervision, Readiness & Autostart

All NEEDS CLARIFICATION resolved below. Each decision records what was chosen,
why, and the alternatives rejected.

## D1. Supervisor mechanism (FR-004)

**Decision**: A small **Bash supervisor loop** (`qmt-supervisor.sh`) launched by
the existing XFCE autostart `.desktop`, running *inside* the RDP session. It
starts `start-mcp.sh`, monitors the child PID, and restarts it with capped
backoff on exit. The QMT client is launched once and (optionally) watched but
not aggressively restarted (a crashed QMT login needs a human anyway).

**Rationale**: MCP and QMT are Wine GUI/X clients — they need the XFCE `DISPLAY`,
which only exists after RDP login. A container-level init (PID 1) cannot own them
without re-architecting the base RDP image. A Bash loop is the lightest thing
that satisfies "restart MCP if it dies" and keeps the repo as the source of truth
(no runtime mutation). It also keeps ordering trivial: detect-broker runs in the
entrypoint *before* the session, so the supervisor always sees resolved config.

**Alternatives rejected**:
- **supervisord** — heavier, another config surface, and still has to live inside
  the session to reach `DISPLAY`; no real gain over a Bash loop for two children.
- **systemd user services** — the base image is not systemd-based; over-engineered.
- **Container PID 1 owns MCP** — breaks because MCP needs the post-login X
  session; would require xvfb-only headless MCP and lose the QMT GUI path.

## D2. QMT-login / xtdata readiness detection (FR-002)

**Decision**: A background **readiness probe thread** in the MCP process polls a
two-signal check on an interval (default 5s):
1. **Filesystem signal** — presence/liveness of QMT `userdata_mini` session
   artifacts under the resolved `QMT_USERDATA_WIN` (cheap, no SDK).
2. **SDK signal** — a cheap `xtdata` call (e.g. a trading-dates/sector probe)
   run through `WorkerPool` with a short timeout; success ⇒ `xtdata: ready`.

The probe drives a small state machine and writes the result onto `HealthState`
(`xtdata`, plus a structured `qmt_login` / `readiness` field). It never blocks
MCP startup.

**Rationale**: The filesystem signal flips fast and cheaply when the operator
logs into 独立交易; the SDK signal confirms xtdata is actually usable (the only
truth that matters to data tools). Polling via `WorkerPool` reuses the existing
bounded-concurrency model and keeps the event loop responsive. Matches
constitution V (serve immediately, gate dependent tools on confirmed readiness).

**Alternatives rejected**:
- **SDK probe only** — slower/heavier each tick and noisier before login.
- **Filesystem only** — files can exist before xtdata is truly ready; false ready.
- **Push/callback from QMT** — no reliable login event is exposed; polling is the
  pragmatic contract (the spec itself says "poll `userdata_mini`/shm + a probe").

## D3. Background trader connector (FR-003)

**Decision**: A background **connector thread** that, *once readiness reports QMT
logged-in*, runs the `xttrader` `start`+`connect` handshake with capped
exponential backoff, is **idempotent** (no-op if already connected), and
**reconnects on drop**. It updates `HealthState.xttrade` to one of
`connected` / `connecting` / `trader-not-ready` / `not_authorized` / `disabled`.
It exposes **no** write tools — it only establishes the session that future 004
query tools (and a later guarded write feature) will consume.

**Rationale**: 005's job per the spec is "auto-drive the xttrader handshake in
the background" and feed readiness to 002's health — decoupled from whether any
trade/query tool exists yet. Building it now means 004 only has to *register
tools* against an already-managed connection.

**Local-validation boundary**: Without broker programmatic permission, `connect()`
fails authorization; the connector must surface `not_authorized` cleanly and keep
the rest of the server healthy (SC-004 of 004, SC-002 of 005 "assuming permission
granted"). We validate: ready-detection → connect-attempt → auth-failure →
`not_authorized` health, and the backoff/idempotency/reconnect logic with a fake.

**Alternatives rejected**:
- **Connect lazily on first query tool call** — defers failure into agent calls,
  hides health truth, and 004 query tools would each need handshake logic.
- **Connect at process start regardless of QMT login** — guaranteed failure spam
  before the human logs in; wrong ordering.

## D4. Docker healthcheck wiring vs. bearer auth (FR-005, Principle VI)

**Decision**: Add an **unauthenticated `/livez`** endpoint that returns only
`{"ok": true|false, "server": "live"}` (no account/broker/secret detail). The
Docker `HEALTHCHECK` and compose `healthcheck:` call `/livez`. The detailed,
state-rich `/healthz` **stays bearer-gated**. A `healthcheck.sh` helper performs
the probe (curl localhost `/livez`, non-zero exit on failure).

**Rationale**: Orchestration needs a credential-free liveness signal, but the
constitution forbids leaking detail on open surfaces. Splitting liveness
(unauth, opaque) from readiness/health (authed, detailed) satisfies both: the
healthcheck reflects "MCP serving" accurately, while nothing sensitive is exposed
without a token. `/livez` up ⇔ the session-supervised MCP is up, which is the
real signal we want (resolves the D1 session-vs-container tension cleanly).

**Alternatives rejected**:
- **Healthcheck curls `/healthz` with the token** — workable but bakes a secret
  into the healthcheck command/inspect output and couples orchestration to auth.
- **Drop auth on `/healthz`** — violates VI; `/healthz` exposes account/readiness
  detail.
- **TCP-port-open check only** — uvicorn can accept TCP while the app is wedged;
  weaker signal than an HTTP 200 from the app.

## D5. tmpfs guard for `/broker` (FR-007)

**Decision**: At the start of `qmt-entrypoint.sh` (before resolving the pack and
before `exec /usr/bin/entrypoint`), detect the filesystem type backing the
`BROKER_MOUNT` (default `/broker`). If it is `tmpfs`, **fail closed by default**
with a clear message; allow an explicit `QMT_ALLOW_TMPFS_BROKER=1` escape hatch
that downgrades to a loud warning.

**Rationale**: 001 burned a RAM-exhaustion crash when the pack/userdata lived on
tmpfs. "Fail closed on ambiguous/unsafe config" is constitutional (Security &
Safety). Doing it in the entrypoint catches it before any heavy QMT/Wine startup.
An escape hatch preserves expert/CI flexibility without making the footgun the
default.

**Detection**: `stat -f -c %T <mount>` (or read `/proc/mounts`) — `tmpfs`/`ramfs`
⇒ unsafe. Cheap, no dependencies.

**Alternatives rejected**:
- **Warn only** — repeats the 001 failure mode for anyone who ignores logs.
- **Hard-block with no override** — breaks legitimate ephemeral CI smoke runs.
- **Check inside the MCP Python** — too late; QMT/Wine may already be thrashing.

## D6. RDP disconnect/reconnect resilience (FR-006)

**Decision**: The supervisor and MCP/QMT processes are children of the XFCE
**session**, not the transient RDP *connection*. Verify the XFCE session (and
thus the supervisor) persists across an RDP client disconnect/reconnect so the
MCP is not torn down. Where the base image ties the session lifetime to the
connection, pin the session to survive (documented in the contract). No new
daemon is introduced; this is a configuration/verification item.

**Rationale**: Wedging the MCP on a dropped RDP client would defeat the whole
"hands-off" goal. The fix is ensuring the right parent/session scope, not adding
machinery.

**Alternatives rejected**:
- **Detach MCP to PID 1** — reintroduces the D1 `DISPLAY` problem.
- **Auto-reconnect RDP** — out of scope; login stays a manual human step.

## D7. Scope boundary — what 005 does NOT do

- No headless/automated QMT **login** (credentials/captcha) — login stays a
  manual RDP step; only *readiness* is automated (spec Out of Scope).
- No write/trade tools — connector establishes the session only (II).
- No multi-instance orchestration / TLS — deferred to a future deploy feature
  (note: the 005 spec's old "006 deploy" reference is stale; 006 turned out to be
  instrument-search, so a dedicated deploy/hardening spec is still unwritten).
