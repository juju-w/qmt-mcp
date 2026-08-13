# Implementation Plan: MCP 2026-07-28 Only

**Branch**: `codex/029-modern-only-mcp` | **Date**: 2026-08-14 | **Spec**:
`specs/029-modern-only-mcp/spec.md`

## Summary

Turn the dual-era protocol foundation into a strict modern-only QMT-MCP 1.0
contract. Add a bounded protocol gate before the official Python server, run
Streamable HTTP statelessly, remove SSE configuration, prevent qmtctl's official
Go SDK from sending fallback lifecycle traffic, and replace legacy conformance
with negative compatibility tests.

## Technical Context

**Language/Version**: Python 3.12; Go 1.25

**Primary Dependencies**: official MCP Python SDK 2.0.0; official MCP Go SDK
1.7.0; Starlette/ASGI; existing qmtctl HTTP transport chain

**Storage**: Existing task SQLite and optional PostgreSQL; no schema change

**Testing**: pytest unit/integration; Go test/vet/build; official MCP
conformance; native linux/amd64 image smoke

**Target Platform**: Linux/Wine appliance and Windows x64 native launcher,
sharing the Python MCP server; qmtctl on six release targets

**Project Type**: MCP HTTP service + Go CLI + packaging/documentation

**Performance Goals**: Protocol rejection adds no body read for valid modern
requests and reads at most 1 MiB only when preserving an invalid request id

**Constraints**: No private SDK patching; no broker needed; auth behavior must
remain unchanged; modern Tasks subscriptions continue using SSE responses to a
POST (not the removed legacy HTTP+SSE transport)

**Scale/Scope**: One MCP endpoint, one core revision, existing tool catalog

## Constitution Check

- **I Broker-agnostic**: Pass. No broker data or paths change.
- **II Read-only default**: Pass. No tool or permission changes.
- **III Reproducible pinned builds**: Pass. Existing stable SDK pins remain.
- **IV Contract-first MCP**: Pass. The accepted and rejected protocol shapes are
  explicit and tested before implementation.
- **V Observable/auditable**: Pass. Health remains available; rejected requests
  never reach tool audit/dispatch.
- **VI Security by default**: Pass. Existing auth runs before detailed MCP
  protocol handling, avoiding unauthenticated capability disclosure.
- **VII Spec-driven delivery**: Pass. Implementation follows this approved 029
  spec and keeps MCP Apps in 030.

Post-design re-check: no constitution exception or complexity waiver is needed.

## Design

### Server protocol gate

Add `ModernProtocolMiddleware` around only the SDK MCP application. For POST
`/mcp`, it accepts exactly `MCP-Protocol-Version: 2026-07-28`; otherwise it
returns JSON-RPC `-32022` with `supported` and `requested`. It reads and replays
at most 1 MiB only for rejected requests so a valid JSON-RPC id can be retained.
The normal modern path remains streaming and untouched.

Construct the SDK Streamable HTTP app with `stateless_http=True`. Keep Tasks
`subscriptions/listen` POST responses as `text/event-stream`; remove only the
old standalone SSE transport option.

### qmtctl policy

Insert a `modernOnlyRoundTripper` immediately outside the MCP SDK transport
chain. It permits MCP HTTP requests only when the protocol header equals
`2026-07-28`; therefore an SDK-generated initialize fallback fails locally.
After `Connect`, verify `InitializeResult().ProtocolVersion` as defense in depth.

### Verification

Replace dual-era integration assertions with:

- modern discovery/list/call and no session id;
- legacy initialize and missing/wrong version rejection;
- modern Tasks/MRTR/subscription regression coverage;
- qmtctl modern success and legacy fixture refusal with no tool call;
- official modern-only conformance selection.

### Release

Update README, client/deployment documentation, skills, feature status, and
changelog-facing migration language. Commit with a Conventional Commits
breaking marker so the existing release workflow calculates `1.0.0`.

## Project Structure

```text
specs/029-modern-only-mcp/
├── spec.md
├── plan.md
├── research.md
├── tasks.md
├── quickstart.md
└── contracts/protocol.md

appliance/mcp/qmt_mcp_core/
├── app.py                    # protocol gate + stateless server assembly
└── config.py                 # remove SSE transport selection

appliance/mcp/tests/
├── integration/test_app_asgi.py
├── integration/test_oauth_authorization.py
└── unit/test_config.py

cli/qmtctl/internal/qmtctl/
├── client.go                 # modern transport policy/version check
├── cli_test.go
└── client_test.go            # modern-only negative coverage

.github/workflows/ci.yml      # modern conformance matrix only
README.md
README.en.md
docs/MCP-CLIENTS.md
appliance/README.md
appliance/docs/DEPLOY.md
skills/
```

**Structure Decision**: Preserve the existing shared Python server and Go CLI
boundaries. Add no service or runtime dependency.

## Complexity Tracking

No constitution violations.
