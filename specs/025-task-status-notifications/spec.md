# Feature Specification: Task Status Notifications

**Feature Branch**: `codex/025-task-status-notifications`

**Created**: 2026-07-31

**Status**: Approved

**Depends on**: 019 (MCP protocol foundation), 020 (tool contracts and
profiles), 021 (OAuth authorization), 022 (pagination and compression), 023
(MCP Tasks), and 024 (task elicitation).

## Summary

Complete the stable MCP Tasks delivery sequence with optional push status
notifications. A capable client opens `subscriptions/listen`, requests one or
more task IDs, receives an acknowledgement, and then receives complete
`notifications/tasks` snapshots as those tasks change.

Stable MCP `2026-07-28` is the preferred protocol. The same `/mcp` endpoint
continues to support deployed 2025 clients and modern clients that have not
implemented Tasks subscriptions. Polling through `tasks/get` remains the
normative fallback; the removed 2025 method `notifications/tasks/status` is
never emitted.

qmtctl uses notifications while waiting when the server acknowledges the
requested task ID. It falls back to the existing bounded polling behavior
after an unsupported subscription, stream loss, or client/server version
mismatch.

This specification supersedes historical roadmap placeholders that named 025
as Resources or Registry publication. Those remain possible later features.

## User Scenarios & Testing

### User Story 1 - Observe a task without polling (Priority: P1)

An agent starts a long-running task, opens one subscription stream for its task
ID, and receives the final result when the task completes.

**Independent Test**: Start the gated `slow_compute` fixture, listen for its
task ID, verify the acknowledgement is the first frame, then verify a complete
`notifications/tasks` terminal snapshot arrives without a `tasks/get` request.

**Acceptance Scenarios**:

1. **Given** a `2026-07-28` client declaring Tasks, **when** it calls
   `subscriptions/listen` with one owned task ID, **then** the first frame is
   `notifications/subscriptions/acknowledged` and echoes that accepted ID.
2. **Given** an accepted working task, **when** the stream is established,
   **then** the server emits a current complete task snapshot after the
   acknowledgement.
3. **Given** the task changes state, **when** the durable transition commits,
   **then** `notifications/tasks` carries the new complete `DetailedTask`
   state.
4. **Given** a completed task, **when** its terminal notification arrives,
   **then** the original tool result is inlined under `result`.
5. **Given** a task fails or is cancelled, **when** its terminal notification
   arrives, **then** it carries the same terminal shape as `tasks/get`.

---

### User Story 2 - Observe elicitation transitions (Priority: P1)

An agent sees that a task needs input, submits part or all of the requested
input, and sees each durable state change on the same stream.

**Independent Test**: Start the gated `multi_input` fixture, subscribe, answer
one request, answer the second request, and verify ordered full snapshots for
`input_required`, partial pending input, `working`, and `completed`.

**Acceptance Scenarios**:

1. **Given** task execution requests input, **when** the pending request map is
   committed, **then** a notification reports `input_required` and the full
   current `inputRequests`.
2. **Given** one of several requests is answered, **when** the remaining map is
   committed, **then** a new `input_required` notification contains only the
   unanswered requests.
3. **Given** the final request is answered, **when** the task resumes, **then**
   a `working` snapshot is emitted before any later terminal snapshot.
4. **Given** a duplicate or unknown response changes no durable state, **when**
   it is acknowledged, **then** no fabricated task transition is emitted.

---

### User Story 3 - Reconnect securely and recover current state (Priority: P1)

A client can reconnect after network loss without missing the task's latest
observable state or seeing another principal's task.

**Independent Test**: Disconnect a listener, let its task advance, reconnect
with the same OAuth principal and verify the current snapshot; request the same
ID from a different principal and verify it is not accepted or disclosed.

**Acceptance Scenarios**:

1. **Given** a listener reconnects with the same principal and sufficient
   scopes, **when** it re-subscribes, **then** it receives the latest current
   snapshot even if transitions occurred while disconnected.
2. **Given** an unknown, expired, cross-principal, or insufficient-scope task
   ID, **when** it is requested, **then** the server does not acknowledge or
   disclose that task.
3. **Given** a mixed list of authorized and unauthorized IDs, **when** the
   stream is acknowledged, **then** only authorized IDs are echoed and
   delivered.
4. **Given** the server restarts, **when** the client reconnects, **then**
   persisted terminal/interrupted state is delivered and old listener state is
   not assumed to survive.
5. **Given** multiple listeners for the same principal and task, **when** the
   task changes, **then** each live listener receives the state independently.

---

### User Story 4 - Existing clients remain predictable (Priority: P1)

Operators can upgrade the service before every MCP host has upgraded.

**Independent Test**: Exercise supported 2025, modern non-declaring, modern
polling-only, and qmtctl fallback paths against the same application.

**Acceptance Scenarios**:

1. **Given** a supported 2025 client, **when** it uses the service, **then**
   existing synchronous behavior remains unchanged.
2. **Given** a modern client that declares Tasks but never calls
   `subscriptions/listen`, **when** it polls, **then** all 023/024 lifecycle
   behavior remains available.
3. **Given** a listener that does not declare Tasks, **when** it requests
   `taskIds`, **then** it receives stable Missing Required Client Capability
   (`-32021`).
4. **Given** qmtctl wait mode, **when** the server acknowledges task
   notifications, **then** qmtctl waits on the stream instead of repeatedly
   polling.
5. **Given** qmtctl cannot establish or loses the stream, **when** the overall
   task deadline remains, **then** it resumes bounded `tasks/get` polling.

## Edge Cases

- `taskIds` is absent, empty, duplicated, malformed, too large, or contains an
  invalid task ID.
- A task reaches a terminal state before, during, or immediately after the
  subscription acknowledgement.
- Snapshot capture races a transition queued after listener registration.
- Completion, cancellation, expiry, and final input submission race.
- A listener disconnects before acknowledgement or while a frame is written.
- A slow consumer fills its bounded event buffer.
- Several state changes occur within the same timestamp millisecond.
- One stream requests task notifications together with standard tool, prompt,
  or resource change notifications.
- An OAuth token refreshes, expires, or loses required scope while a stream is
  open.
- A task is deleted by TTL before a reconnect.
- A client retries `subscriptions/listen` with the same or a new JSON-RPC ID.
- qmtctl receives an acknowledgement without its requested task ID, malformed
  SSE, a graceful close, or an abrupt transport close.

## Requirements

### Functional Requirements

- **FR-001**: Task notifications MUST target stable MCP `2026-07-28`, SEP-2575
  `subscriptions/listen`, and SEP-2663 `notifications/tasks`.
- **FR-002**: The server MUST NOT emit the removed
  `notifications/tasks/status` method.
- **FR-003**: Supported 2025 clients, modern non-declaring clients, and clients
  that choose polling MUST preserve existing 019-024 behavior on `/mcp`.
- **FR-004**: `taskIds` MUST be an optional extension field under
  `params.notifications`; standard subscription filters MUST continue to work
  alone or in the same listen request.
- **FR-005**: A listen request containing `taskIds` MUST require the client to
  declare `io.modelcontextprotocol/tasks`, otherwise return `-32021`.
- **FR-006**: The first stream frame MUST be
  `notifications/subscriptions/acknowledged`, stamped with the listen request
  ID, and contain only accepted notification filters and task IDs.
- **FR-007**: Task IDs MUST be validated, deduplicated in request order, and
  bounded to at most 64 IDs per stream.
- **FR-008**: Unknown, expired, cross-principal, and insufficient-scope IDs
  MUST be treated indistinguishably and MUST NOT be acknowledged or delivered.
- **FR-009**: After acknowledgement, the server MUST emit one current snapshot
  for every accepted task ID, including tasks already terminal.
- **FR-010**: Every emitted `notifications/tasks` params object MUST be a
  complete `DetailedTask` shape equivalent to `tasks/get`, excluding the
  response-only `resultType` discriminator.
- **FR-011**: Every notification and acknowledgement MUST carry
  `_meta["io.modelcontextprotocol/subscriptionId"]` equal to the originating
  listen request ID.
- **FR-012**: Every observable durable transition MUST publish only after it
  commits: input request, partial input update, resume, completion, protocol
  failure, tool-error completion, and cancellation.
- **FR-013**: A request that produces no durable state change MUST NOT invent a
  status notification.
- **FR-014**: Per-task transition order MUST be preserved for each live
  listener. Duplicate current snapshots are permissible, but an older state
  MUST NOT overwrite a newer state in qmtctl.
- **FR-015**: Each listen stream MUST have a bounded event backlog. A stream
  that cannot keep up MUST be closed without blocking task execution or other
  listeners.
- **FR-016**: Disconnect cleanup MUST promptly remove listener state; server
  shutdown MUST permit a graceful `SubscriptionsListenResult` where the
  transport remains writable.
- **FR-017**: Listener state MUST remain in memory only. Reconnect recovery
  MUST come from the durable task store's current snapshot, not replay logs.
- **FR-018**: OAuth/static-token principal ownership and original tool scopes
  MUST be checked before acknowledging each task ID.
- **FR-019**: A listener MUST never receive task arguments, raw input
  responses, credentials, principal digests, or other storage-only fields.
- **FR-020**: qmtctl wait mode MUST attempt one task subscription after task
  creation, accept only matching full snapshots, and retain the existing
  overall `--task-timeout`.
- **FR-021**: qmtctl MUST fall back to server-guided polling when notifications
  are unsupported, unacknowledged, malformed, gracefully closed before a
  terminal state, or lost after acknowledgement.
- **FR-022**: qmtctl OAuth access MUST be refreshed before opening a listen
  request; it MUST NOT print tokens or subscription metadata containing
  credentials.
- **FR-023**: Unit and integration tests MUST cover initial snapshots, every
  transition, ordering, mixed filters, multiple listeners, races,
  backpressure, disconnect cleanup, OAuth isolation, and qmtctl fallback.
- **FR-024**: CI MUST run the pinned official
  `tasks-status-notifications` scenario and record its result. While the pinned
  harness marks that scenario pending, project integration tests MUST provide
  the executable acceptance gate.
- **FR-025**: Existing 019-024 conformance, Python/Go tests, six-target CLI
  builds, release policy, secret scan, and native linux/amd64 image gates MUST
  remain green.
- **FR-026**: README, MCP client, CLI, operator, test, AGENT, and skill
  documentation MUST present `2026-07-28` as preferred and notifications as an
  optional optimization over polling.

## Key Entities

- **Task Subscription Filter**: The bounded requested and accepted `taskIds`
  carried inside a stable `subscriptions/listen` filter.
- **Task State Event**: An in-process immutable snapshot published after a
  durable transition.
- **Task Status Notification**: The `notifications/tasks` wire message carrying
  one complete client-visible task state.
- **Listen Stream**: One long-lived response stream identified by its
  originating JSON-RPC request ID.
- **Current Snapshot**: The latest authorized task record emitted after
  acknowledgement to make reconnect recovery independent of replay.
- **Polling Fallback**: Existing `tasks/get` behavior used when push delivery
  is unavailable or interrupted.

## Success Criteria

- **SC-001**: An integration client receives acknowledgement, current working
  state, and terminal result for `slow_compute` without issuing `tasks/get`.
- **SC-002**: The elicitation test observes `input_required`, partial pending
  input, `working`, and `completed` in durable transition order.
- **SC-003**: Cross-principal, insufficient-scope, unknown, and expired IDs
  disclose no task data in acknowledgement or later frames.
- **SC-004**: A reconnect after a missed transition receives the latest
  persisted state as its first task snapshot.
- **SC-005**: A saturated or disconnected listener does not delay transition
  commit by more than one event-loop checkpoint and leaves no registered
  listener after cleanup.
- **SC-006**: qmtctl completes a notification-backed wait with no task polls,
  and completes the same workflow through polling when the listen surface is
  unavailable.
- **SC-007**: Existing modern Tasks, supported 2025, OAuth, pagination,
  compression, release, and image gates remain green.

## Assumptions

- MCP `2026-07-28` is the latest stable protocol at implementation time and is
  the documented primary line.
- Client support will lag server support; notifications therefore remain an
  optional optimization and polling remains supported indefinitely.
- The appliance runs one MCP process. Cross-replica pub/sub is outside this
  feature, though the internal event publisher remains replaceable.
- The pinned official conformance scenario is currently pending its
  `subscriptions/listen` harness rewrite, so project integration coverage is
  required rather than treating a skip as a pass.
