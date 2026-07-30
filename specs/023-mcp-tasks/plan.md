# Implementation Plan: MCP Tasks

**Branch**: `codex/023-mcp-tasks` | **Date**: 2026-07-31 |
**Spec**: `specs/023-mcp-tasks/spec.md`

## Summary

Add stable MCP Tasks lifecycle and durable SQLite state for selected
long-running QMT tools, preserve synchronous old-client behavior, and extend
qmtctl with automatic waiting plus explicit task operations.

## Technical Context

**Language/Version**: Python 3.12 and Go 1.25.

**Primary Dependencies**: MCP Python SDK 2.0.0, MCP Go SDK 1.7.0, Starlette
1.3.1, Python stdlib SQLite.

**Storage**: SQLite at `/broker/cache/mcp-tasks-v1.sqlite3` by deployed default;
bounded terminal retention and TTL cleanup.

**Testing**: Dependency-light store tests, official-SDK integration tests, Go
test/vet/build, selected official stable Tasks conformance, release-policy
checks, actionlint, six-target cross-build, native linux/amd64 image smoke.

**Target Platform**: Windows Python 3.12 under Wine on linux/amd64; qmtctl on
Linux/macOS/Windows amd64/arm64.

**Project Type**: MCP HTTP service plus Go CLI.

**Performance Goals**: Return a committed task handle without waiting for QMT
work; task lookup/poll persistence under 20 ms at 1,000 retained records; no
poll faster than server-provided guidance.

**Constraints**: No broker pack in CI; no credential or argument persistence;
task ownership must survive OAuth refresh; old clients remain synchronous.

**Scale/Scope**: Six production long-running tools, three Tasks methods, one
SQLite store, four CLI task commands, seven non-MRTR conformance scenarios.

## Constitution Check

- **I Broker-agnostic**: PASS. Lifecycle and conformance tests use gated fake
  tools and no proprietary broker pack.
- **II Read-only default**: PASS. Tasks change execution lifecycle, not tool
  permissions or trading surfaces.
- **III Reproducible pinned builds**: PASS. Existing pinned SDKs expose the
  needed generic extension APIs.
- **IV Contract-first MCP**: PASS. Stable wire fields and errors are documented
  before implementation.
- **V Observable/readiness-gated**: PASS. Durable states make long operations
  inspectable and interrupted work explicit.
- **VI Security by default**: PASS. IDs are unguessable; ownership and scopes
  are enforced; arguments and credentials are excluded from storage.
- **VII Spec-driven delivery**: PASS. Work follows spec, research, plan, tasks,
  implementation, and verification.

## Project Structure

```text
specs/023-mcp-tasks/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
├── quickstart.md
├── data-model.md
├── VERIFICATION.md
├── contracts/
│   └── tasks-extension.md
└── checklists/
    └── requirements.md

appliance/mcp/
├── qmt_mcp_core/
│   ├── app.py
│   ├── config.py
│   ├── task_store.py
│   └── tasks_extension.py
└── tests/
    ├── unit/
    └── integration/

cli/qmtctl/internal/qmtctl/
├── client.go
├── root.go
├── task.go
└── task_test.go
```

**Structure Decision**: Keep persistence in a dependency-light core module,
put protocol adaptation in one official-SDK extension, and isolate qmtctl task
resolution in the current transport/client package.

## Implementation Phases

1. Add configuration, data model, schema migration, and store unit tests.
2. Implement stable Tasks method bindings, lifecycle transitions, ownership,
   cleanup, restart recovery, and cancellation.
3. Wire allowlisted production tools and gated conformance fixture tools
   through the official Python SDK interceptor.
4. Validate task HTTP routing headers inside the authenticated MCP path.
5. Add qmtctl capability declaration, wait/detach/sync behavior, custom task
   commands, per-request limits, and overall task timeout.
6. Add modern, legacy, OAuth, restart, retention, cancellation, header, and CLI
   integration tests.
7. Add seven official stable Tasks scenarios to CI.
8. Update compose, operator, client, CLI, and skill documentation.
9. Run all local, conformance, cross-build, policy, and native image gates.

## Compatibility Strategy

- Primary: MCP `2026-07-28` with `io.modelcontextprotocol/tasks`.
- Secondary: supported 2025 protocol revisions continue direct synchronous
  `tools/call` on the same endpoint.
- Modern clients without Tasks also remain synchronous for QMT production
  tools.
- Stable wire fields and error `-32021` are authoritative. Unreleased
  ext-tasks draft changes are tracked but not emitted.

## Complexity Tracking

The qmtctl transport adapter is necessary because official Go SDK 1.7.0 can
declare extensions and invoke custom methods but does not yet decode the task
variant of `tools/call`. It remains bounded to Tasks envelopes and passes all
ordinary MCP traffic through unchanged.
