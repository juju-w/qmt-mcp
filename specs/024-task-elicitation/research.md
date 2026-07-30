# Research: Task Elicitation

## Decision 1: Stable `2026-07-28` is primary; compatibility is negotiated

**Decision**: Implement multi-round task input only for negotiated MCP
`2026-07-28` sessions declaring `io.modelcontextprotocol/tasks`. Preserve the
same synchronous compatibility paths used by 019 and 023.

**Rationale**: `2026-07-28` is the stable contract, but host support remains
uneven. Capability negotiation is more reliable than maintaining product-name
allowlists or a second endpoint.

## Decision 2: Model task input as standard request envelopes

**Decision**: Persist `inputRequests` as a keyed map whose values contain
`method` and `params`. Begin with `elicitation/create`, while keeping the
coordinator method-agnostic enough for another standard MRTR request kind.

**Rationale**: SEP-2663 composes Tasks with standard MCP requests. Reusing their
wire shapes lets clients dispatch them with existing elicitation/sampling
implementations and avoids an incompatible QMT prompt protocol.

## Decision 3: Use an in-memory interaction coordinator plus durable snapshot

**Decision**: A live `TaskInteraction` owns pending waiters, fulfilled
responses, and lifetime-used keys. SQLite stores only the current pending
request snapshot and lifecycle status.

**Rationale**: Execution needs a wakeable async primitive, while reconnecting
clients need a durable point-in-time prompt. Raw answers may contain sensitive
information and are unnecessary after delivery. Since 023 deliberately does
not persist tool arguments, it cannot safely replay execution after restart;
waiting tasks therefore retain deterministic interruption failure.

Rejected alternatives:

- Polling SQLite from each runner adds latency and still needs cancellation
  coordination.
- Persisting responses enables replay but retains sensitive user input.
- A global response queue loses task ownership and complicates races.

## Decision 4: Partial updates are idempotent and atomic

**Decision**: Under one per-task async lock, match only currently pending keys,
remove matched requests from the durable snapshot, and wake execution only
when none remain. Unknown, already-satisfied, duplicate, and terminal-task keys
are acknowledged and ignored after authorization.

**Rationale**: Clients can retry after network loss and can answer requests
incrementally. Idempotent acknowledgements prevent accidental double execution.
The lock aligns in-memory delivery with one durable state transition.

## Decision 5: Keep response bounds strict but forward-compatible

**Decision**: Bound each round to 16 requests, each key and method to 128
characters, and each compact request or response batch to 64 KiB. Validate the
known elicitation response action while retaining JSON-compatible content.

**Rationale**: Inputs arrive over an authenticated endpoint but are still
untrusted. Explicit limits prevent database and memory amplification. The
standard envelope leaves room for future methods without widening storage
unboundedly.

## Decision 6: Resolve synchronous MRTR before task creation

**Decision**: For a tool declared as MRTR-before-task, let the first call reach
the tool and return `InputRequiredResult` directly. On a retry carrying
`inputResponses`, create the durable task and execute the tool using the
official SDK context.

**Rationale**: This is the SEP-2663 composition rule and the official
`tasks-mrtr-composition` expectation. Creating the task first would strand an
orphan and incorrectly attach a task ID to the initial input request.

## Decision 7: qmtctl remains explicit, not interactive-by-default

**Decision**: Keep automatic waiting non-interactive. At `input_required`, show
the task ID and pending requests; accept answers only through explicit
`qmtctl task update --responses-json`.

**Rationale**: Prompts may be confirmations for consequential actions. A CLI
must not infer acceptance or block unattended automation on stdin. The
existing JSON command is scriptable and auditable by the caller.

## Decision 8: Validate with the official MRTR scenarios

**Decision**: Add `tasks-mrtr-input` and `tasks-mrtr-composition` to the pinned
official conformance matrix while retaining all seven 023 scenarios.

**Rationale**: The scenarios precisely cover standard input request envelopes,
resume after update, partial fulfillment, and MRTR-to-task composition.

## Primary Sources

- MCP stable versioning:
  https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning
- MCP Tasks overview:
  https://modelcontextprotocol.io/extensions/tasks/overview
- SEP-2663 Tasks extension:
  https://modelcontextprotocol.io/seps/2663-tasks-extension
- MCP elicitation:
  https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation
- Official MCP conformance:
  https://github.com/modelcontextprotocol/conformance
- Official Python SDK v2.0.0:
  https://github.com/modelcontextprotocol/python-sdk/tree/v2.0.0
