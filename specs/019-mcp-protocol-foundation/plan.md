# Implementation Plan: MCP Protocol Foundation

**Branch**: `codex/019-mcp-protocol-foundation` | **Date**: 2026-07-31 |
**Spec**: `specs/019-mcp-protocol-foundation/spec.md`

## Summary

Establish MCP 2026-07-28 as the preferred stateless production path while
preserving all current legacy clients. Migrate the server and qmtctl to stable
official SDKs, pin both runtimes, and add dual-era conformance checks to CI.

## Technical Context

**Language/Version**: Python 3.12, Go 1.25, Node.js for the official conformance
runner.

**Primary Dependencies**: official MCP Python SDK 2.0.0, official MCP Go SDK
1.7.0, uvicorn 0.52.0, official MCP conformance 0.2.0-alpha.10.

**Storage**: N/A.

**Testing**: pytest unit/integration, Go test/vet/build, official MCP
conformance, actionlint, release-policy unit tests.

**Target Platform**: Windows Python 3.12 under Wine on linux/amd64; qmtctl on
Linux/macOS/Windows amd64/arm64; GitHub Actions ubuntu-latest.

**Project Type**: MCP HTTP service plus Go CLI.

**Performance Goals**: No additional request round trips beyond the mandatory
initialize notification; no rebuild of the Wine dependency layer for source-only
changes.

**Constraints**: No broker pack or xtquant in CI; no new production tools;
modern and legacy eras share one authenticated endpoint.

**Scale/Scope**: One dual-era server endpoint, one modern-first CLI client,
selected modern and legacy conformance scenarios, one Python lock and one Go
module lock.

## Constitution Check

- **I Broker-agnostic**: PASS. Conformance uses xtdata disabled and no broker
  files.
- **II Read-only default**: PASS. No tool surface changes.
- **III Reproducible pinned builds**: PASS and improved by the committed lock.
- **IV Contract-first MCP**: PASS. Wire behavior is specified in
  `contracts/protocol.md`.
- **V Observable/readiness-gated**: PASS. Existing health and audit remain.
- **VI Security by default**: PASS. Production auth is unchanged; loopback
  unauthenticated mode exists only in the CI process.
- **VII Spec-driven delivery**: PASS. Implementation follows this approved spec,
  research, plan, and task list.

## Project Structure

```text
specs/019-mcp-protocol-foundation/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
├── quickstart.md
├── VERIFICATION.md
└── contracts/
    └── protocol.md

appliance/
├── Dockerfile
└── mcp/
    ├── requirements.in
    ├── requirements.txt
    └── tests/integration/test_app_asgi.py

cli/qmtctl/
├── cmd/conformance/main.go
└── internal/qmtctl/
    ├── client.go
    └── cli_test.go

.github/workflows/ci.yml
```

**Structure Decision**: Keep production code in the existing MCP and qmtctl
packages. The conformance adapter is a separate test executable so the shipped
root CLI surface does not change.

## Implementation Phases

1. Add dual-era server/client integration tests and the conformance adapter.
2. Migrate FastMCP registration and transport assembly to official Python SDK
   2.0.0 without changing the business tool set.
3. Migrate qmtctl MCP calls to official Go SDK 1.7.0 and update Go 1.25 builders.
4. Pin direct runtime dependencies and compile the transitive Python 3.12 lock.
5. Switch Docker and CI integration setup to the lock.
6. Add pinned official modern and legacy server/client conformance checks.
7. Add a cached native linux/amd64 image gate shared by CI and release.
8. Run host checks, target-lock validation, image build smoke, and document
   evidence.

## Complexity Tracking

No constitution violations.
