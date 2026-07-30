# Implementation Plan: MCP Pagination and HTTP Compression

**Branch**: `codex/022-mcp-pagination-compression` | **Date**: 2026-07-31 |
**Spec**: `specs/022-mcp-pagination-compression/spec.md`

## Summary

Add deterministic, authorization-aware cursor pagination to `tools/list`, make
qmtctl aggregate all pages with abuse bounds, and negotiate gzip for eligible
MCP JSON responses without compressing SSE.

## Technical Context

**Language/Version**: Python 3.12 and Go 1.25.

**Primary Dependencies**: MCP Python SDK 2.0.0, Starlette 1.3.1, MCP Go SDK
1.7.0.

**Storage**: None. Cursors are self-contained and contain no secrets.

**Testing**: Dependency-light pytest, official-SDK integration pytest, Go
test/vet/build, official MCP conformance, release-policy checks, actionlint,
six-target cross-build, native linux/amd64 image smoke.

**Target Platform**: Windows Python 3.12 under Wine on linux/amd64; qmtctl on
Linux/macOS/Windows amd64/arm64.

**Project Type**: MCP HTTP service plus Go CLI.

**Performance Goals**: Bound tool-list pages to 50 definitions by default;
reduce gzip-eligible catalog responses by at least 40 percent; add no extra
round trips when the visible catalog fits one page.

**Constraints**: No broker pack in CI; no tool surface change; OAuth filtering
must precede pagination; SSE must remain incremental and uncompressed.

**Scale/Scope**: One paginated MCP list method, two environment settings, one
bounded CLI aggregator, modern and legacy tests.

## Constitution Check

- **I Broker-agnostic**: PASS. All tests use core/fake tools.
- **II Read-only default**: PASS. No tool calls or trading capabilities change.
- **III Reproducible pinned builds**: PASS. No dependency change is required.
- **IV Contract-first MCP**: PASS. Cursor and compression contracts are
  documented before implementation.
- **V Observable/readiness-gated**: PASS. Health and audit behavior are
  unchanged.
- **VI Security by default**: PASS. Pagination follows authorization and
  malformed cursors fail closed.
- **VII Spec-driven delivery**: PASS. Work follows spec, research, plan, tasks,
  implementation, and verification.

## Project Structure

```text
specs/022-mcp-pagination-compression/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
├── quickstart.md
├── VERIFICATION.md
├── contracts/
│   └── pagination-compression.md
└── checklists/
    └── requirements.md

appliance/mcp/
├── qmt_mcp_core/
│   ├── app.py
│   ├── config.py
│   └── pagination.py
└── tests/
    ├── unit/
    └── integration/

cli/qmtctl/internal/qmtctl/
├── client.go
└── cli_test.go
```

**Structure Decision**: Keep cursor encoding in a dependency-light core module,
wire it through the existing authorized server subclass, and keep CLI
aggregation in the current client package.

## Implementation Phases

1. Add config and cursor unit tests.
2. Implement bounded keyset cursor encoding, validation, and pagination.
3. Override the SDK list handler after OAuth visibility and apply cache hints.
4. Add negotiated gzip around the MCP transport app.
5. Make qmtctl aggregate pages with cycle/page/duplicate guards.
6. Add modern, legacy, gzip, SSE, and CLI integration tests.
7. Update compose, operator, client, and skill documentation.
8. Run all local, conformance, cross-build, policy, and native image gates.

## Complexity Tracking

The private-named SDK handler override is isolated to the existing
`AuthorizedMCPServer` subclass. It is required because Python SDK 2.0.0 accepts
pagination params but its public high-level server has no page-size or
pagination callback.
