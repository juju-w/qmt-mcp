# Implementation Plan: Task Elicitation

**Branch**: `codex/024-task-elicitation` | **Date**: 2026-07-31 |
**Spec**: `specs/024-task-elicitation/spec.md`

## Summary

Complete stable task-internal multi-round input and MRTR-to-Tasks composition,
backed by the 023 task store, while keeping old clients synchronous and making
qmtctl responses explicit and bounded.

## Technical Context

**Language/Version**: Python 3.12 and Go 1.25.

**Primary Dependencies**: MCP Python SDK 2.0.0, MCP Go SDK 1.7.0, Pydantic,
Python asyncio and contextvars, SQLite from the standard library.

**Storage**: Existing `/broker/cache/mcp-tasks-v1.sqlite3`; only current pending
request snapshots are durable, never response values.

**Testing**: Task store unit tests, official-SDK integration tests, OAuth and
legacy regressions, Go CLI tests, pinned official MRTR conformance, six-target
cross-build, actionlint and native linux/amd64 image smoke.

**Target Platform**: Windows Python 3.12 under Wine on linux/amd64; qmtctl on
Linux/macOS/Windows amd64/arm64.

**Project Type**: MCP HTTP service plus Go CLI.

**Performance Goals**: Commit a task input transition under 20 ms at 1,000
retained tasks; resume within one event-loop turn after the final response; no
polling loop inside task execution.

**Constraints**: No broker pack in CI; no response persistence; no automatic
confirmation; terminal states remain immutable; old clients remain
synchronous.

**Scale/Scope**: One reusable interaction coordinator, existing three Tasks
methods, three gated fixtures, two additional official conformance scenarios,
and bounded qmtctl validation.

## Constitution Check

- **I Broker-agnostic**: PASS. Runtime and tests do not depend on proprietary
  QMT files.
- **II Read-only default**: PASS. No production write tool gains a prompt or
  permission; fixture deletion is synthetic and CI-gated.
- **III Reproducible pinned builds**: PASS. Existing pinned SDKs expose the
  stable context and result types.
- **IV Contract-first MCP**: PASS. Standard request/response envelopes, bounds,
  and state transitions are specified before implementation.
- **V Observable/readiness-gated**: PASS. Pending requests remain visible by
  task ID without logging answer values.
- **VI Security by default**: PASS. Ownership/scopes are rechecked; responses
  are bounded, transient, and excluded from storage/logging.
- **VII Spec-driven delivery**: PASS. 024 remains isolated from 025 status
  notifications and future Apps work.

## Project Structure

```text
specs/024-task-elicitation/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
├── quickstart.md
├── data-model.md
├── VERIFICATION.md
├── contracts/
│   └── task-elicitation.md
└── checklists/
    └── requirements.md

appliance/mcp/
├── qmt_mcp_core/
│   ├── app.py
│   ├── task_store.py
│   └── tasks_extension.py
└── tests/
    ├── unit/
    └── integration/

cli/qmtctl/internal/qmtctl/
├── client.go
├── task.go
└── task_test.go
```

**Structure Decision**: Keep durable mutations in `TaskStore`, put the
async interaction coordinator beside the existing Tasks extension, and avoid
another service or database table. qmtctl remains in its current transport and
task command package.

## Implementation Phases

1. Add store operations for replacing a pending snapshot and atomically
   resuming only from `input_required`.
2. Add request/response validation, `TaskInteraction`, per-task locks, wake-up,
   cancellation, and cleanup.
3. Expose a context-local reusable input helper to task-running tools.
4. Replace the 023 fixture shortcut with real async `confirm_delete` and
   `multi_input` flows.
5. Add MRTR-before-task routing and a context-aware
   `test_tool_with_task` fixture using official SDK result types.
6. Harden qmtctl response parsing and input-required rendering.
7. Add unit, integration, OAuth, compatibility, race, and data-leak tests.
8. Add both official stable MRTR scenarios to CI.
9. Update README, MCP client, CLI, operator, test, and skill documentation.
10. Run complete local, conformance, cross-build, policy, and image gates.

## Compatibility Strategy

- Preferred: MCP `2026-07-28` plus declared
  `io.modelcontextprotocol/tasks`, with complete task elicitation.
- Supported fallback: 2025 protocol revisions retain direct synchronous
  `tools/call`.
- Modern clients without Tasks retain 023 synchronous production behavior.
- qmtctl does not infer host support from a product name and never
  auto-confirms.
- No development-draft revision, method, or error code is emitted.

## Complexity Tracking

The in-memory coordinator is necessary because a suspended coroutine needs
single-delivery wake-up and cancellation, while SQLite remains the durable
client-visible snapshot. The split is bounded: one coordinator per live task,
one lock, one future, and no replay queue.
