# Feature Specification: Deploy & Security Hardening

**Status**: Draft (P1 — open-source launch)
**Depends on**: 002 (bearer auth, `/healthz`), 005 (`/livez`, healthcheck), 009 (SECURITY.md)

## Summary

Give operators a safe, documented way to deploy the appliance beyond a loopback
dev box. Today `docker-compose.yml` binds the MCP and RDP ports directly, ships a
weak default RDP password (`qmt`), and has no TLS/reverse-proxy story — fine for
local dev, risky if exposed. This feature adds a **hardening guide**, a
**reverse-proxy + TLS example**, and an **operator pre-flight check** that flags
weak/insecure configuration before exposure. The 005 spec's stale "006 deploy"
reference is superseded by this feature.

## User Scenarios

### US1 — Operator deploys beyond localhost (P1)
**Acceptance**: A `DEPLOY.md` explains the threat model and the recommended
topology: MCP behind a TLS reverse proxy with a strong bearer token; RDP not
exposed to the public internet (tunnel/VPN/loopback only).

### US2 — TLS termination example (P1)
**Acceptance**: A working reverse-proxy example (Caddy) terminates TLS and
forwards to the MCP container; a compose override wires it without changing the
base image.

### US3 — Pre-flight catches weak config (P1)
**Acceptance**: A `harden-check.sh` flags: default/short bearer token, default RDP
password, MCP bound to `0.0.0.0` without a proxy, and missing TLS — exiting
non-zero so it can gate a deploy in CI/automation.

## Functional Requirements

- **FR-001**: `DEPLOY.md` — threat model, network topology, token strength, RDP
  exposure guidance, TLS options, and a deploy checklist.
- **FR-002**: A reverse-proxy example (`deploy/Caddyfile.example`) terminating TLS
  and proxying to MCP, forwarding the bearer `Authorization` header.
- **FR-003**: A compose override (`docker-compose.tls.yml`) that adds the proxy and
  keeps the MCP port internal (not host-published) — base image unchanged.
- **FR-004**: `harden-check.sh` — pure-shell pre-flight: weak token (default or
  `<32` chars), default RDP password, public `0.0.0.0` bind hint, TLS reminder;
  non-zero exit on any hard failure, warnings otherwise. Reads `.env`/env only;
  prints/leaks no secret values.
- **FR-005**: Document **token rotation** (change `QMT_MCP_TOKEN`, restart MCP) and
  that rotation invalidates existing agent sessions.
- **FR-006**: Reaffirm constitution VI: no raw trading endpoint on an open LAN;
  secrets never in images/git.

## Success Criteria

- **SC-001**: `docker-compose.tls.yml` parses as valid compose/YAML.
- **SC-002**: `harden-check.sh` passes `bash -n`, exits non-zero for a weak token
  and zero for a strong, proxied config (verified with sample env).
- **SC-003**: `DEPLOY.md` checklist covers token, RDP, TLS, exposure, audit.

## Out of Scope / Deferred

- Multi-instance orchestration / k8s manifests (separate effort).
- Automated certificate management beyond the Caddy example.
- mTLS / OIDC (future, if demanded).

## Assumptions / Dependencies

- The appliance build/run is amd64-only; examples are validated by syntax/parse
  here, not a live run.
- 005 provides `/livez` for the proxy/orchestration health path.
