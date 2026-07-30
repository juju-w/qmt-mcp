# Feature Specification: Task Elicitation

**Feature Branch**: `codex/024-task-elicitation`

**Created**: 2026-07-31

**Status**: Approved

**Depends on**: 019 (MCP protocol foundation), 020 (tool contracts and
profiles), 021 (OAuth authorization), 022 (pagination and compression), 023
(MCP Tasks).

## Summary

Complete the stable MCP `2026-07-28` multi-round task input flow. A long-running
tool can pause as `input_required`, expose one or more standard MCP requests,
accept partial or complete answers through `tasks/update`, resume, and repeat
without losing task identity.

Also implement the stable MRTR-to-Tasks composition rule: synchronous
multi-round tool input is resolved before task creation, then the retried call
becomes a task whose eventual result uses the supplied answer.

The same `/mcp` endpoint remains dual-line compatible. Full task elicitation is
advertised and exercised only for negotiated `2026-07-28` clients declaring
Tasks. Supported 2025 clients and modern clients without Tasks keep the
synchronous behavior established by 019 and 023. qmtctl exposes pending
requests and requires explicit operator answers; it never auto-accepts them.

This specification supersedes historical roadmap placeholders that named 024
as MCP Apps. Apps remain a possible later feature, outside the 019-025 delivery
sequence.

## User Scenarios & Testing

### User Story 1 - A task pauses for explicit input (Priority: P1)

A task-running tool asks for confirmation, the client observes
`input_required`, submits an answer, and receives the final result under the
same task ID.

**Independent Test**: Start the gated `confirm_delete` fixture through a modern
Tasks client, poll its standard elicitation request, accept it through
`tasks/update`, and poll to completion.

**Acceptance Scenarios**:

1. **Given** a working task requests input, **when** the request is committed,
   **then** `tasks/get` reports `input_required` and a non-empty
   `inputRequests` map.
2. **Given** a pending request, **when** the client responds with its exact key,
   **then** `tasks/update` returns only `{"resultType":"complete"}` and task
   execution receives the response.
3. **Given** all pending requests are answered, **when** execution resumes,
   **then** status returns to `working` before reaching a terminal state.
4. **Given** accepted confirmation, **when** the fixture completes, **then**
   its final ordinary tool result reflects the confirmed operation.
5. **Given** decline or cancel, **when** the tool handles that action, **then**
   no implicit acceptance is invented by the server.

---

### User Story 2 - Multiple requests can be answered incrementally (Priority: P1)

A task presents several independent prompts and a client answers only the ones
it can currently satisfy.

**Independent Test**: Start the gated `multi_input` fixture, answer one of two
request keys, verify only the unanswered key remains, then answer it and
complete the task.

**Acceptance Scenarios**:

1. **Given** two pending requests, **when** one valid response is submitted,
   **then** the task remains `input_required`.
2. **Given** partial fulfillment, **when** the task is read, **then**
   `inputRequests` contains only unanswered requests.
3. **Given** unknown or already-satisfied response keys, **when** they are sent
   with an authorized known task, **then** they are acknowledged and ignored.
4. **Given** the last pending request is answered, **when** the update commits,
   **then** the task resumes exactly once.
5. **Given** a later input round, **when** it requests input, **then** every key
   remains unique over that task's lifetime.

---

### User Story 3 - Synchronous input composes with later task execution (Priority: P1)

A tool first needs immediate user input and then starts long-running work.

**Independent Test**: Call the gated `test_tool_with_task` fixture without
input, receive a core `InputRequiredResult`, retry with the echoed response,
receive a Task result, and verify the completed task result includes the
provided name.

**Acceptance Scenarios**:

1. **Given** no initial user name, **when** the tool is first called, **then**
   it returns `resultType: "input_required"` with no task ID.
2. **Given** a valid initial response, **when** the same tool call is retried,
   **then** it returns `resultType: "task"` with no stale `inputRequests` or
   `requestState`.
3. **Given** the task completes, **when** its result is read, **then** it
   contains the supplied name.
4. **Given** the initial MRTR round, **when** it returns before task creation,
   **then** no orphan task record is inserted.

---

### User Story 4 - Existing clients stay predictable (Priority: P1)

Operators can continue using older Codex, Claude Code, WorkBuddy, Cline, or
qmtctl versions against the same deployment.

**Independent Test**: Repeat existing 2025 and modern non-declaring tool calls
and compare their direct synchronous results before and after 024.

**Acceptance Scenarios**:

1. **Given** a supported 2025 client, **when** it calls a production tool,
   **then** the server keeps direct synchronous behavior.
2. **Given** a `2026-07-28` client without Tasks, **when** it calls a
   task-capable production tool, **then** the server keeps the 023 synchronous
   fallback.
3. **Given** qmtctl reaches `input_required`, **when** automatic wait is active,
   **then** it stops safely, prints the task ID and pending requests, and never
   guesses an answer.
4. **Given** explicit `qmtctl task update --responses-json`, **when** the
   response document is malformed or oversized, **then** the CLI fails before
   sending it.

## Edge Cases

- `inputRequests` is empty, malformed, oversized, contains an unsupported
  method envelope, or reuses a key from an earlier round.
- `inputResponses` is empty, partial, malformed, oversized, entirely unknown,
  or mixes pending and unknown keys.
- Cancellation, completion, failure, and the final input response race.
- Two clients answer the same pending key concurrently.
- A client retries the same `tasks/update` after losing the acknowledgement.
- The server restarts while execution awaits input.
- A terminal task receives late or duplicate responses.
- OAuth credentials refresh or scopes narrow between prompt and response.
- A task's pending request snapshot is read while another response commits.
- The MRTR retry omits, mutates, or duplicates the expected response.

## Requirements

### Functional Requirements

- **FR-001**: Full task elicitation MUST target stable MCP `2026-07-28` and the
  `io.modelcontextprotocol/tasks` extension; no draft protocol revision or
  draft error code may replace the stable contract.
- **FR-002**: Supported 2025 sessions and modern sessions not declaring Tasks
  MUST preserve existing synchronous behavior on the same endpoint.
- **FR-003**: Each task `inputRequests` entry MUST be a standard MCP request
  envelope with a bounded unique key and `{method, params}`.
- **FR-004**: The first supported request kind MUST be
  `elicitation/create`; the runtime design MUST permit future standard request
  methods without inventing QMT-specific wire methods.
- **FR-005**: A task requesting input MUST atomically enter
  `input_required`, persist the current request snapshot, and expose only
  pending requests through `tasks/get`.
- **FR-006**: `tasks/update` MUST authenticate the task owner, re-check original
  scopes, accept a bounded `inputResponses` map, and return the acknowledgement
  `{"resultType":"complete"}`.
- **FR-007**: Responses MUST be correlated by exact request key. Unknown,
  duplicate, already-satisfied, and terminal-task response keys MUST be
  acknowledged and ignored after task authorization.
- **FR-008**: Partial fulfillment MUST remove only answered requests and keep
  the task `input_required`; satisfying the final pending request MUST
  atomically return it to `working` and wake execution once.
- **FR-009**: A task MAY perform multiple input rounds, but request keys MUST
  be unique for the full in-process lifetime of that task.
- **FR-010**: Cancellation or any terminal transition MUST wake or cancel an
  input waiter, and a late response MUST NOT overwrite terminal state.
- **FR-011**: Pending request prompts MAY be stored in the existing task
  database; raw input responses MUST NOT be persisted, audited, logged, or
  included in status messages.
- **FR-012**: Restart recovery MUST retain 023 behavior: every stored
  `working` or `input_required` task becomes failed with `-32603`; execution
  and sensitive responses are not replayed.
- **FR-013**: Request count, request key length, method length, per-round JSON
  payload, response count, and response JSON payload MUST have explicit bounds
  enforced before durable mutation.
- **FR-014**: Malformed requests or responses MUST fail with Invalid Params
  (`-32602`) without leaking task existence or internal stack data.
- **FR-015**: The task execution API MUST be reusable by future production QMT
  tools and MUST not hard-code conformance fixture names into lifecycle state
  transitions.
- **FR-016**: MRTR-to-Tasks composition MUST resolve a core
  `InputRequiredResult` before task creation, and taskify only the retried call
  that carries valid `inputResponses`.
- **FR-017**: The retried MRTR call's task result MUST use the supplied response
  and MUST not expose stale `requestState` or `inputRequests` on its Task
  result.
- **FR-018**: qmtctl automatic wait MUST stop at `input_required`, render the
  task ID and request map in human and JSON modes, and require explicit
  `task update --responses-json` to continue.
- **FR-019**: qmtctl MUST validate response JSON as an object and enforce the
  same practical count and payload bounds before transport.
- **FR-020**: Conformance-only `confirm_delete`, `multi_input`, and
  `test_tool_with_task` fixtures MUST remain behind
  `QMT_MCP_TASK_CONFORMANCE_FIXTURES=1`.
- **FR-021**: CI MUST pass official stable `tasks-mrtr-input` and
  `tasks-mrtr-composition` scenarios in addition to all 023 Tasks scenarios.
- **FR-022**: Unit and integration tests MUST cover partial fulfillment,
  retries, unknown keys, concurrent responses, cancellation races, OAuth
  isolation, restart recovery, and modern/legacy compatibility.
- **FR-023**: Client, operator, CLI, and skill documentation MUST identify
  `2026-07-28` as preferred, explain fallback, and show explicit safe response
  flows without encouraging automatic confirmation.

## Key Entities

- **Task Input Round**: One bounded set of simultaneously pending standard MCP
  requests associated with an active task.
- **Input Request Key**: A client-visible correlation key unique for the
  in-process lifetime of a task.
- **Pending Input Snapshot**: The durable point-in-time map returned by
  `tasks/get`.
- **Input Response Batch**: A client-provided map correlated to one or more
  pending keys and delivered only to live task execution.
- **Task Interaction**: The in-memory coordinator between task execution,
  durable lifecycle state, `tasks/update`, cancellation, and timeouts.
- **MRTR Composition Call**: A synchronous initial input exchange that is
  resolved before the subsequent tool execution becomes a task.

## Success Criteria

- **SC-001**: Official `tasks-mrtr-input` passes all three stable checks and
  `tasks-mrtr-composition` passes its stable check without expected failures.
- **SC-002**: A two-request task remains `input_required` after one answer,
  exposes only the second request, then completes after the second answer.
- **SC-003**: Duplicate, unknown, and late responses are idempotent and never
  restart execution or mutate a terminal result.
- **SC-004**: No input response value appears in SQLite, audit output, logs, or
  task status messages in security regression tests.
- **SC-005**: Existing 023 Tasks scenarios, supported 2025 conformance,
  qmtctl behavior, OAuth isolation, and restart tests remain green.
- **SC-006**: Python, Go, six-target CLI build, release-policy, actionlint,
  secret review, and native linux/amd64 image gates remain green.

## Assumptions

- MCP `2026-07-28` is the latest stable protocol at implementation time and is
  the preferred documented line.
- Some production MCP clients have not yet implemented Tasks or task
  elicitation, so compatibility is capability-driven rather than inferred from
  product names.
- 024 supplies infrastructure and gated fixtures; adding input prompts to a
  production QMT tool requires a later tool-specific contract and safety
  review.
- One appliance process owns each task database. Cross-process task execution
  coordination is outside this feature.
