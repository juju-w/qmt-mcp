# Implementation Plan: Task Status Notifications

**Branch**: `codex/025-task-status-notifications` | **Date**: 2026-07-31 |
**Spec**: `specs/025-task-status-notifications/spec.md`

## Summary

Add stable, secure task-state push over the existing MCP listen stream, publish
complete snapshots after durable task transitions, and make qmtctl prefer
notifications while retaining server-guided polling fallback.

## Technical Context

**Language/Version**: Python 3.12 and Go 1.25.

**Primary Dependencies**: MCP Python SDK 2.0.0, MCP Go SDK 1.7.0, mcp-types
2.0.0, Pydantic, AnyIO, asyncio, SQLite, and Go net/http.

**Storage**: Existing `/broker/cache/mcp-tasks-v1.sqlite3`; subscriptions and
event queues are in memory only.

**Testing**: Notification handler and lifecycle unit tests, real ASGI
Streamable HTTP integration, OAuth isolation, qmtctl SSE/fallback tests,
existing conformance, six-target builds, actionlint, and image smoke.

**Target Platform**: Windows Python 3.12 under Wine on native linux/amd64;
qmtctl on Linux/macOS/Windows amd64/arm64.

**Performance Goals**: Publish a transition without network blocking; send an
in-process notification within one event-loop turn; no repeated `tasks/get`
from qmtctl when a healthy subscription is acknowledged.

**Constraints**: One `/mcp` endpoint; no SDK fork; no task replay log; no
arguments or input responses in events; old clients remain compatible.

**Scale/Scope**: At most 64 task IDs per stream, bounded concurrent streams,
bounded per-stream queues, and the existing 1,000 retained-task default.

## Constitution Check

- **I Broker-agnostic**: PASS. Notifications use the task runtime and no broker
  files.
- **II Read-only default**: PASS. No new QMT write surface is introduced.
- **III Reproducible pinned builds**: PASS. Pinned SDKs and standard libraries
  are retained; no dependency fork is added.
- **IV Contract-first MCP**: PASS. Stable methods, filters, snapshots, errors,
  and bounds are specified before implementation.
- **V Observable/readiness-gated**: PASS. Authorized task status becomes more
  observable without exposing arguments or answers.
- **VI Security by default**: PASS. Acknowledgement and delivery both derive
  from owner/scope authorization and bounded input.
- **VII Spec-driven delivery**: PASS. 025 is limited to task status
  subscriptions and closes the 019-025 sequence.

## Project Structure

```text
specs/025-task-status-notifications/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
├── quickstart.md
├── data-model.md
├── VERIFICATION.md
├── contracts/
│   └── task-status-notifications.md
└── checklists/
    └── requirements.md

appliance/mcp/
├── qmt_mcp_core/
│   ├── app.py
│   ├── task_notifications.py
│   ├── task_store.py
│   └── tasks_extension.py
└── tests/
    ├── unit/
    └── integration/
        └── test_task_notifications.py

cli/qmtctl/internal/qmtctl/
├── client.go
├── task.go
├── task_notifications.go
├── task_notifications_test.go
└── task_test.go
```

**Structure Decision**: Keep lifecycle ownership in `TasksExtension`, isolate
listen-stream concerns in `task_notifications.py`, and leave SQLite unchanged.
The shared SDK subscription bus fans out immutable events to the replacement
listen handler.

## Implementation Phases

1. Define typed task subscription filters, immutable state events, complete
   notification params, and bounded constants.
2. Add a Tasks-aware listen handler that preserves standard SDK subscriptions,
   validates capability and task IDs, filters authorization, acknowledges
   first, and emits current snapshots.
3. Install the handler through the low-level registration API while sharing
   the MCPServer subscription bus.
4. Add a transition publisher to task creation, input request/replacement,
   resume, completion, failure, and cancellation paths.
5. Add unit tests for wire shapes, bounds, ordering, no-op updates, mixed
   filters, slow consumers, cleanup, and race outcomes.
6. Add real Streamable HTTP integration for acknowledgement, current snapshot,
   terminal state, elicitation, reconnect, OAuth isolation, and legacy
   compatibility.
7. Add qmtctl's extension-aware SSE reader and notification-first wait with
   safe polling fallback.
8. Add qmtctl tests for no-poll success, unsupported acknowledgement, stream
   loss, malformed frames, OAuth headers, and overall timeout.
9. Add the official pending scenario to CI traceability and retain every
   existing 019-024 scenario.
10. Update user, client, operator, test, AGENT, and skill documentation.
11. Run local, conformance, cross-build, policy, secret, compose, and image
   gates; deliver through PR, main CI, and automated release.

## Compatibility Strategy

- Preferred: MCP `2026-07-28`, declared Tasks, and
  `subscriptions/listen.notifications.taskIds`.
- Modern polling: declared Tasks with `tasks/get`; no notification requirement.
- Modern non-declaring: synchronous production behavior.
- Supported 2025: existing initialize/session and synchronous behavior.
- qmtctl: notification-first wait, automatic polling fallback, explicit
  `detach` and `sync` modes unchanged.
- Never emit the removed `notifications/tasks/status` vocabulary.

## Complexity Tracking

The project-owned listen handler is required because the pinned official
Python SDK honors only core subscription filter keys. It is bounded to one
module, uses the SDK's public registration/session APIs and shared bus, and is
tested against mixed standard-plus-task filters. The Go SSE reader is required
because the pinned Go SDK has no extension carrier on its unexported listen
helper; all ordinary task RPCs remain on the SDK.
