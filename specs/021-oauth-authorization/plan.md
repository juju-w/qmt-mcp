# Implementation Plan: OAuth Authorization

**Branch**: `codex/021-oauth-authorization` | **Date**: 2026-07-31 |
**Spec**: `specs/021-oauth-authorization/spec.md`

## Summary

Add a fail-closed JWT/JWKS verifier and standard MCP resource-server wiring,
reuse registry metadata for request-specific tool scopes, and add qmtctl
authorization-code login with secure local session persistence.

## Technical Context

**Language/Version**: Python 3.12, official MCP Python SDK 2.0.0, PyJWT 2.13;
Go 1.25, official MCP Go SDK 1.7.0.

**Storage**: qmtctl user-config JSON session store only; no server-side identity
database.

**Testing**: dependency-light policy/config tests, official-runtime JWT/ASGI
integration tests, Go OAuth fixture tests, existing modern/legacy conformance,
actionlint, cross-build, native linux/amd64 image.

**Constraints**:

- Static bearer behavior remains the default.
- No token value or OAuth session may enter audit output.
- No trade-capable tool or scope may be introduced.
- Preferred protocol is 2026-07-28; legacy behavior remains automatic.
- JWKS fetching must be bounded and independent of token claims.

## Constitution Check

- **I Broker-agnostic**: PASS. OAuth configuration contains no broker data.
- **II Read-only default**: PASS. Authorization narrows existing tools and adds
  no trading capability.
- **III Reproducible builds**: PASS. PyJWT/cryptography and Go OAuth are already
  pinned transitively; direct declarations will be locked.
- **IV Contract-first MCP**: PASS. RFC 9728 metadata and standard challenges
  are explicit contracts.
- **V Observable/readiness-gated**: PASS. Health remains protected; auth status
  exposes mode, never credentials.
- **VI Security by default**: PASS. JWT checks and scope intersections fail
  closed.
- **VII Spec-driven delivery**: PASS.

## Project Structure

```text
specs/021-oauth-authorization/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
├── quickstart.md
├── VERIFICATION.md
├── contracts/
│   └── oauth.md
└── checklists/
    └── requirements.md

appliance/mcp/qmt_mcp_core/
├── auth.py
├── app.py
├── config.py
├── registry.py
└── tool_contracts.py

cli/qmtctl/internal/qmtctl/
├── auth.go
├── client.go
└── cli.go
```

## Implementation Phases

1. Add auth-mode, issuer/JWKS/audience/algorithm, timeout/cache, and scope
   configuration with fail-closed validation.
2. Implement static/JWT/composite token verifiers and bounded JWKS retrieval.
3. Wire official SDK resource-server auth and standards-compliant metadata.
4. Extend registry metadata and MCP server dispatch with per-token tool scope
   filtering and call enforcement.
5. Add modern HTTP insufficient-scope challenges and legacy handler fallback.
6. Add qmtctl callback, browser launch, registration options, atomic session
   store, login/status/logout, refresh persistence, and automatic saved login.
7. Update deployment, client, CLI, skills, and env documentation.
8. Run all local, conformance, build, and release-policy gates and record
   verification evidence.

## Complexity Tracking

The server auth module isolates security-sensitive token and challenge logic.
The scoped MCP subclass exists because the SDK's standard list implementation
is process-global while authorization is request-specific. qmtctl persistence
is isolated from CLI dispatch so refresh rotation can be tested independently.
