# Feature Specification: Supervision, Readiness & Autostart

**Status**: Draft (lightweight backlog draft)
**Depends on**: 001 (base + pack), 002 (MCP core health)

## Summary

Make the appliance robust and hands-off: supervise the long-running pieces
(xrdp desktop, QMT terminal, MCP server), auto-launch QMT + MCP on RDP login,
detect when QMT is logged in/ready, auto-drive the xttrader handshake in the
background, and expose readiness so a docker healthcheck reflects true state.
Hardens the ad-hoc autostart used during the 001 prototype.

## User Scenarios

### US1 - One-login startup (P1)
**Acceptance**:
1. Given a fresh container + mounted pack, when the operator logs in over RDP, then the QMT terminal and the MCP server both auto-start.
2. Given the operator logs into QMT (独立交易), when QMT becomes ready, then the MCP trader connector auto-connects (no manual init/start/connect) and `/healthz` flips to ready.
3. Given the container is recreated, then the above still holds with no manual hot-fixes (recreate-safe).

### US2 - Self-healing & health (P2)
**Acceptance**:
1. If the MCP server process dies, it is restarted by the supervisor.
2. A docker healthcheck reports unhealthy when the MCP endpoint is down and healthy when serving.
3. Readiness probe distinguishes: xrdp up / QMT logged in / xtdata ready / trader connected.

## Functional Requirements
- **FR-001**: XFCE-session autostart for QMT client (`start-qmt.sh`) and MCP (`start-mcp.sh`), baked into the image (recreate-safe; no runtime injection).
- **FR-002**: Readiness detection for QMT login — poll `userdata_mini`/shm + an xtdata/xttrader probe — and surface it to 002's `/healthz`.
- **FR-003**: Background trader connector with retry/backoff that auto-runs start+connect once QMT is ready; idempotent; reconnects on drop.
- **FR-004**: Process supervision (e.g. a lightweight supervisor) for MCP (+ optional QMT) with restart policy; ordered so detect-broker (001) runs first.
- **FR-005**: Docker `HEALTHCHECK` wired to `/healthz` (or an MCP ping) so orchestration sees real state.
- **FR-006**: Resilient to RDP disconnect/reconnect (session restart does not wedge the MCP).
- **FR-007**: Resource guardrails: ensure broker pack/userdata live on real disk (NOT tmpfs); document and, if feasible, warn at startup if `/broker` is on tmpfs (lesson from 001).

## Success Criteria
- **SC-001**: From a clean recreate, RDP login → QMT + MCP both running, with zero manual steps.
- **SC-002**: After QMT 独立交易 login, trader connects automatically within the retry interval (assuming broker permission granted).
- **SC-003**: Killing the MCP process results in automatic restart within N seconds.
- **SC-004**: docker healthcheck reflects MCP up/down accurately.

## Out of Scope / Deferred
- Headless/automated QMT *login* (credentials/captcha) — login stays manual over RDP.
- Multi-instance orchestration / TLS (006 deploy).

## Assumptions / Dependencies
- 002 exposes `/healthz`; 001 resolves paths + runs detect-broker first.
- QMT login is a manual human step (interactive); only readiness is automated.
- A startup guard checks `/broker` is not on tmpfs (prevents the RAM-exhaustion
  crash seen in the 001 prototype).
