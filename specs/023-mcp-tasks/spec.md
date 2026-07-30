# Feature Specification: MCP Tasks

**Feature Branch**: `codex/023-mcp-tasks`

**Created**: 2026-07-31

**Status**: Approved

**Depends on**: 019 (MCP protocol foundation), 020 (tool contracts and
profiles), 021 (OAuth authorization), 022 (pagination and compression).

## Summary

Implement the MCP Tasks extension from the stable `2026-07-28` protocol for
long-running QMT tools. A capable client can start work, receive a durable task
handle immediately, reconnect, poll, cancel, and retrieve the terminal tool
result without keeping one HTTP request open.

Keep synchronous `tools/call` as the compatibility path for clients using a
2025 protocol revision or not declaring the Tasks extension. qmtctl supports
wait, detach, and forced synchronous modes while preserving existing command
output in its default wait mode.

This feature establishes task lifecycle and storage. Multi-round structured
input is specified by 024, and task status notifications are specified by 025.

## User Scenarios & Testing

### User Story 1 - A long tool call becomes a durable task (Priority: P1)

An MCP `2026-07-28` client declares `io.modelcontextprotocol/tasks`, invokes an
eligible long-running tool, and receives a task handle before the work
finishes.

**Independent Test**: Invoke a delayed fixture tool, assert the initial
`working` handle, poll it through `tasks/get`, and compare its nested terminal
result with the fixture's ordinary tool result.

**Acceptance Scenarios**:

1. **Given** a modern client declaring Tasks and an eligible tool, **when**
   `tools/call` is accepted, **then** the server durably records the task before
   returning a flat task handle.
2. **Given** a working task, **when** the client calls `tasks/get`, **then** it
   receives current timestamps, status, TTL, poll guidance, and no premature
   terminal result.
3. **Given** successful tool completion, **when** the task is polled, **then**
   status is `completed` and the ordinary MCP tool result is nested under
   `result`.
4. **Given** an application-level tool error represented by `isError: true`,
   **when** work finishes, **then** the task is `completed` and preserves that
   tool result.
5. **Given** an MCP protocol exception, **when** work finishes, **then** the
   task is `failed` and exposes the structured JSON-RPC error.

---

### User Story 2 - A task survives client disconnects (Priority: P1)

An operator starts a long download, closes qmtctl, then uses the task ID from a
later process to inspect or wait for it.

**Independent Test**: Start a task in detach mode, create a second qmtctl
client, and wait for the same task to finish.

**Acceptance Scenarios**:

1. **Given** detach mode, **when** a task starts, **then** qmtctl prints a
   machine-readable task handle without polling.
2. **Given** a known task ID, **when** another qmtctl process runs `task get`
   or `task wait`, **then** it resumes through standard Tasks methods.
3. **Given** a server process restart while work is active, **when** the stored
   task is next read, **then** it is terminal `failed` with an interruption
   error rather than remaining `working` forever.
4. **Given** a completed task and a server restart, **when** it is read before
   expiry, **then** its terminal result is preserved.

---

### User Story 3 - A principal controls only its own tasks (Priority: P1)

OAuth and hybrid deployments bind every task to the authenticated MCP
principal and required tool scopes.

**Independent Test**: Create a task as one OAuth subject, then attempt get,
update, and cancel using another subject and using a token missing the original
tool scope.

**Acceptance Scenarios**:

1. **Given** a task created under OAuth, **when** its owner reconnects with a
   refreshed token containing the required scopes, **then** access succeeds.
2. **Given** another principal or insufficient scopes, **when** it addresses
   the task ID, **then** the server returns Invalid Params (`-32602`) without
   revealing whether the task exists.
3. **Given** static-token mode, **when** an authenticated client resumes a
   task, **then** it uses the deployment's single static principal.
4. **Given** an unauthenticated task request, **when** it reaches the MCP
   endpoint, **then** existing authentication challenges are unchanged.

---

### User Story 4 - Operators can cancel and bound retained work (Priority: P1)

An operator cancels a task and the server retains only bounded, non-expired
task history.

**Independent Test**: Cancel a delayed task, assert immutable `cancelled`
status, advance the configured expiry, and verify the task becomes unknown.

**Acceptance Scenarios**:

1. **Given** a non-terminal task, **when** `tasks/cancel` is accepted, **then**
   it becomes terminal `cancelled` immediately and execution receives a
   best-effort cancellation signal.
2. **Given** a terminal task, **when** completion or cancellation races arrive,
   **then** its first terminal state remains immutable.
3. **Given** an expired or unknown task ID, **when** any task method addresses
   it, **then** the server returns `-32602`.
4. **Given** retained history above the configured bound, **when** cleanup
   runs, **then** expired and oldest terminal tasks are removed while active
   tasks remain.

---

### User Story 5 - Existing clients remain synchronous (Priority: P1)

A current Codex, Claude Code, WorkBuddy, or qmtctl installation that has not
upgraded its MCP tools continues using the same server endpoint.

**Independent Test**: Invoke an eligible delayed tool through a 2025 session
and through a modern session without the extension, then compare the direct
results.

**Acceptance Scenarios**:

1. **Given** a 2025 client, **when** it calls an eligible tool, **then** the
   server returns the direct synchronous result.
2. **Given** a `2026-07-28` client that does not declare Tasks, **when** it
   calls a task-capable QMT tool, **then** the server returns the direct
   synchronous result.
3. **Given** a tool that requires task execution in the conformance fixture,
   **when** a modern client omits the extension, **then** the server returns
   stable error `-32021` with required capability data.
4. **Given** qmtctl's default wait mode, **when** a task completes, **then**
   existing human and JSON output shows the final tool result rather than a
   transport-specific wrapper.

## Edge Cases

- A task ID is empty, oversized, malformed, unknown, expired, or owned by a
  different principal.
- Work completes, fails, or requests input at the same moment as cancellation.
- The client disconnects before receiving the initial task handle.
- SQLite is unavailable, read-only, corrupt, or cannot create its parent
  directory.
- The server restarts while tasks are working, input-required, or terminal.
- A client sends `tasks/get`, `tasks/update`, or `tasks/cancel` without
  declaring the extension.
- `Mcp-Method` or `Mcp-Name` is absent or disagrees with the JSON-RPC body.
- A tool returns `isError: true` instead of raising an MCP protocol error.
- qmtctl's per-request timeout elapses while the overall task remains valid.
- OAuth credentials refresh during a long qmtctl polling loop.

## Requirements

### Functional Requirements

- **FR-001**: The server MUST advertise the stable
  `io.modelcontextprotocol/tasks` extension for negotiated MCP `2026-07-28`
  sessions and MUST NOT advertise it for supported 2025 revisions.
- **FR-002**: The production task-capable allowlist MUST default to
  `qmt_xtdata_download_history`, `qmt_xtdata_download_history_batch`,
  `qmt_xtdata_download_financial_data`, `qmt_xtdata_formula_call_batch`,
  `qmt_xtdata_formula_generate_factor`, and
  `qmt_xtdata_refresh_instrument_cache`.
- **FR-003**: A modern client declaring Tasks and calling an allowlisted tool
  MUST receive a flat `resultType: "task"` handle after the task record is
  committed and before execution completes.
- **FR-004**: A 2025 client, a modern non-declaring client, or a non-allowlisted
  tool MUST retain direct synchronous `tools/call` behavior.
- **FR-005**: The server MUST implement `tasks/get`, `tasks/update`, and
  `tasks/cancel`; it MUST NOT invent `tasks/list` or `tasks/result`.
- **FR-006**: Task states MUST be limited to `working`, `input_required`,
  `completed`, `failed`, and `cancelled`, with terminal states immutable.
- **FR-007**: `tasks/get` MUST return `resultType: "complete"` plus the stable
  task wire fields and include nested `result`, `error`, or `inputRequests`
  only when applicable.
- **FR-008**: An application tool result with `isError: true` MUST complete the
  task; a raised MCP error MUST fail the task and preserve its code, message,
  and safe data.
- **FR-009**: Task IDs MUST use cryptographically secure randomness, be
  unguessable, and be bounded before storage lookup.
- **FR-010**: Persistent storage MUST record lifecycle data, owner digest,
  required scopes, and terminal output but MUST NOT record tool arguments,
  bearer tokens, authorization headers, or raw principal identifiers.
- **FR-011**: OAuth and hybrid tasks MUST be bound to a digest of the SDK's
  stable principal components and re-check original tool scopes on every task
  method.
- **FR-012**: Unauthorized, unknown, malformed, or expired task references MUST
  be indistinguishable Invalid Params (`-32602`) responses.
- **FR-013**: Active records discovered after restart MUST become terminal
  `failed` with Internal Error (`-32603`); terminal records MUST survive until
  expiry or bounded cleanup.
- **FR-014**: Cancellation MUST be immediate and immutable at the protocol
  layer and MUST send best-effort cancellation to in-process execution.
- **FR-015**: Configuration MUST expose enablement, store path, TTL, poll
  interval, maximum retained terminal tasks, and the task-capable tool
  allowlist with bounded startup validation.
- **FR-016**: Task persistence MUST default to
  `/broker/cache/mcp-tasks-v1.sqlite3` in the deployed appliance and use
  owner-only filesystem permissions where supported.
- **FR-017**: The HTTP transport MUST validate stable Tasks routing headers:
  `Mcp-Method` must identify the task method and `Mcp-Name` must equal the
  bounded body `taskId`; mismatches MUST fail before dispatch.
- **FR-018**: A modern client invoking a task-required method without declaring
  Tasks MUST receive stable Missing Required Client Capability error `-32021`
  with required capability data.
- **FR-019**: qmtctl MUST support `--task-mode wait|detach|sync`, default to
  `wait`, and accept equivalent environment configuration.
- **FR-020**: qmtctl MUST provide `task get`, `task wait`, `task cancel`, and
  `task update --responses-json` commands using official SDK extension
  registration and custom method dispatch.
- **FR-021**: qmtctl wait mode MUST poll no faster than server guidance, use a
  separate overall task timeout, preserve per-request timeouts, and refresh
  OAuth authorization for each poll.
- **FR-022**: qmtctl detach mode MUST expose the task ID and status without
  polling; sync mode MUST omit the extension so the server performs the
  compatibility call.
- **FR-023**: Conformance-only fixture tools MUST be gated by
  `QMT_MCP_TASK_CONFORMANCE_FIXTURES=1` and MUST never appear in normal
  production configuration or documentation.
- **FR-024**: CI MUST pass the official stable Tasks lifecycle, capability,
  wire-field, request-state, request-header, dispatch-envelope, and
  required-task-error scenarios without a broker pack.
- **FR-025**: Multi-round task input and status notifications MUST remain
  explicitly deferred to specs 024 and 025 without incompatible placeholder
  methods.
- **FR-026**: Operator, client, CLI, and skill documentation MUST describe
  stable-first behavior, old-client fallback, persistence, cancellation,
  retention, and recovery.

## Key Entities

- **Task Record**: Durable lifecycle metadata and terminal output for one
  accepted tool execution.
- **Task Principal**: A non-reversible digest binding a task to one authenticated
  MCP identity or the single static-token deployment identity.
- **Task Handle**: The stable, flat initial response containing task ID,
  timestamps, status, TTL, and polling guidance.
- **Terminal Outcome**: An ordinary MCP tool result, an MCP protocol error, or
  cancellation.
- **Task Policy**: The bounded configuration controlling eligible tools,
  storage, TTL, polling, and retention.

## Success Criteria

- **SC-001**: Official stable Tasks lifecycle and six related non-MRTR
  conformance scenarios pass in CI.
- **SC-002**: A detached task can be resumed by a new qmtctl process and returns
  the same final tool result as default wait mode.
- **SC-003**: Cross-principal and insufficient-scope access tests always return
  `-32602` without task metadata leakage.
- **SC-004**: Restart tests preserve terminal outcomes and convert every
  non-terminal stored task to deterministic `-32603` failure.
- **SC-005**: Existing modern non-extension and supported 2025 tool calls remain
  byte-equivalent at the JSON result level.
- **SC-006**: Python, Go, OAuth, official conformance, six-target CLI,
  release-policy, and native linux/amd64 image gates remain green.

## Assumptions

- MCP `2026-07-28` is the current stable revision and the primary advertised
  behavior; development drafts are not compatibility targets.
- SQLite on the persistent `/broker` volume is sufficient for one appliance
  process and bounded task history.
- Long-running QMT calls may execute in worker processes or synchronous
  threads. Cancellation is therefore a reliable protocol state transition and
  a best-effort execution signal, not a guarantee that an external broker call
  stops instantly.
- Full argument replay after an appliance restart would require persisting
  sensitive tool inputs. This feature deliberately fails interrupted active
  work instead.

## Out of Scope And Follow-on Delivery

- `tasks/list`, `tasks/result`, distributed queues, or multi-node workers.
- Persisting or replaying tool arguments after server restart.
- Multi-round structured elicitation was delivered in 024; URL-mode input
  remains future work.
- Task status subscription and notification delivery was delivered in 025.
- Taskifying short read-only snapshot, account, or discovery tools.
