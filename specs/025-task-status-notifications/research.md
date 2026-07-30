# Research: Task Status Notifications

## Decision 1: Use the stable 2026 notification vocabulary

**Decision**: Implement `notifications/tasks` over
`subscriptions/listen` for MCP `2026-07-28`.

**Rationale**: SEP-2663 defines task notifications as an extension of the
stable SEP-2575 listen stream. The similarly named
`notifications/tasks/status` type belongs to the removed 2025 Tasks draft and
is intentionally excluded from the modern SDK method tables.

Rejected alternatives:

- Emit `notifications/tasks/status`: incompatible with the stable extension.
- Push on the original `tools/call` response: the task outlives that request
  and the current spec gives it a dedicated listen channel.
- Add a second SSE endpoint: duplicates MCP transport and auth semantics.

## Decision 2: Preserve polling as a complete fallback

**Decision**: Notifications are optional. `tasks/get` remains fully supported,
and qmtctl returns to bounded polling whenever the listen path is unavailable
or lost.

**Rationale**: Existing Codex, Claude Code, WorkBuddy, and other MCP clients
may negotiate older versions or may support Tasks without task subscriptions.
Capability-driven behavior allows the service to upgrade first without
product-name heuristics.

## Decision 3: Extend the SDK listen handler locally

**Decision**: Add a project-owned Tasks-aware listen handler that supports both
the SDK's standard subscription events and the Tasks extension on the same
stream. Reuse the official in-memory subscription bus and wire/session APIs.

**Rationale**: MCP Python SDK 2.0.0 preserves unknown subscription-filter
fields but its built-in `ListenHandler` deliberately honors only core tool,
prompt, and resource events. Its event union likewise has no Tasks extension
event. A narrow local handler avoids patching installed dependencies while
retaining the SDK's transport routing and request-ID stamping.

The low-level SDK's public `add_request_handler` registration API replaces the
default `subscriptions/listen` handler after MCPServer construction. This
private-server access is isolated to `AuthorizedMCPServer`.

## Decision 4: Publish immutable complete task snapshots

**Decision**: Each committed transition publishes an immutable `TaskStateEvent`
containing the client-visible task snapshot and owner identity. The listener
serializes it as a full `DetailedTask` without `resultType`.

**Rationale**: Full snapshots let clients replace local state without applying
patches, match `tasks/get`, and satisfy SEP-2663. Publishing after commit means
a reconnect or concurrent poll sees the same or newer state.

Rejected alternatives:

- Publish only `{taskId,status}`: insufficient for input and terminal output.
- Publish deltas: creates replay/order dependencies.
- Fetch from SQLite only when draining: a fast later transition could collapse
  a required intermediate state such as resumed `working`.

## Decision 5: Acknowledge only authorized task IDs

**Decision**: Validate and deduplicate up to 64 requested IDs, then acknowledge
only records owned by the current principal for which the current token still
contains every original tool scope. Unknown and unauthorized IDs are omitted
identically.

**Rationale**: The acknowledgement itself is observable data. Filtering before
the first frame prevents task-existence probing while allowing one request to
contain a mix of valid and stale IDs.

## Decision 6: Subscribe before snapshotting, acknowledge before delivery

**Decision**: Register the event listener first, capture current authorized
snapshots second, send the acknowledgement third, then send current snapshots
and drain buffered transitions.

**Rationale**: No transition can disappear between snapshot capture and live
registration. The one writer coroutine guarantees the acknowledgement remains
the first frame. A state that races snapshot capture may be delivered twice,
which is harmless because notifications are complete idempotent snapshots.

## Decision 7: Bound and isolate slow consumers

**Decision**: Limit open streams and give each a bounded in-memory event queue.
If the queue fills, close only that stream and require the client to reconnect
and refetch.

**Rationale**: Task execution must never await network delivery. There is no
replay promise, so preserving an unbounded stale backlog provides less value
than cleanly forcing current-state recovery.

## Decision 8: Let qmtctl use raw stable SSE for the extension field

**Decision**: qmtctl opens a bounded raw Streamable HTTP listen request for one
task ID, parses acknowledgement and task frames, and falls back to its existing
official-SDK `tasks/get` path.

**Rationale**: MCP Go SDK 1.7.0 supports the core listen method but its
`NotificationSubscriptions` struct has no extension-field carrier and its
listen helper is not exported. A small extension-aware SSE reader is less
invasive than forking the SDK. It reuses qmtctl's OAuth token source and keeps
all task methods on the official SDK.

## Decision 9: Treat the official scenario skip honestly

**Decision**: Run pinned
`@modelcontextprotocol/conformance@0.2.0-alpha.10`
`tasks-status-notifications`, record its current pending skip, and enforce real
behavior with project integration tests.

**Rationale**: The scenario source explicitly says its harness awaits a
`subscriptions/listen` rewrite. A skipped optional scenario is useful
traceability, but it cannot serve as acceptance evidence.

## Primary Sources

- MCP Tasks overview:
  https://modelcontextprotocol.io/extensions/tasks/overview
- SEP-2663 Tasks extension:
  https://modelcontextprotocol.io/seps/2663-tasks-extension
- MCP `2026-07-28` transports:
  https://modelcontextprotocol.io/specification/2026-07-28/basic/transports
- TypeScript SDK `2026-07-28` migration:
  https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/migration/support-2026-07-28.md
- Official Python SDK v2.0.0:
  https://github.com/modelcontextprotocol/python-sdk/tree/v2.0.0
- Official Go SDK v1.7.0:
  https://github.com/modelcontextprotocol/go-sdk/tree/v1.7.0
- Official MCP conformance:
  https://github.com/modelcontextprotocol/conformance
