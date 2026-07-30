# Research: MCP Tasks

## Decision 1: Target stable `2026-07-28`, preserve synchronous fallback

**Decision**: Implement Tasks only for negotiated MCP `2026-07-28` sessions.
Keep the existing synchronous `tools/call` path for supported 2025 sessions
and modern clients that have not declared the extension.

**Rationale**: Tasks is an extension in the current stable protocol, while
many deployed MCP hosts have not upgraded. Stable-first behavior exposes the
new capability without forcing an ecosystem-wide migration or creating a
second endpoint.

The stable Missing Required Client Capability code is `-32021`. The ext-tasks
development branch currently discusses `-32003`; that draft value is a watch
item, not an implementation target.

## Decision 2: Use the official Python SDK extension API

**Decision**: Register an `mcp.server.Extension` with method bindings for
`tasks/get`, `tasks/update`, and `tasks/cancel`, plus a `tools/call`
interceptor for allowlisted tools.

**Rationale**: MCP Python SDK 2.0.0 exposes extension registration,
version-gated custom methods, capability checks, and tool-call interception.
It does not yet include a Tasks runtime, so the application supplies lifecycle
and storage while leaving session negotiation and JSON-RPC dispatch to the
official SDK.

## Decision 3: Store lifecycle state in bounded SQLite

**Decision**: Add a dependency-light SQLite task store. Commit a task before
returning its handle; retain terminal output, principal digest, required
scopes, timestamps, and expiry; never persist tool arguments or credentials.

**Rationale**: SQLite matches the single-appliance deployment, survives
client/server reconnects, uses the existing persistent `/broker` volume, and
adds no network service. Not storing arguments keeps secrets and private
strategy inputs out of a resumable queue. Active work interrupted by restart
is marked failed deterministically.

Rejected alternatives:

- In-memory-only tasks lose handles and terminal results on every restart.
- Redis/PostgreSQL add deployment services not justified by one appliance.
- Persisting arguments enables replay but expands the sensitive-data surface.

## Decision 4: Bind tasks to principal and original scopes

**Decision**: Hash the official SDK principal components
`(client_id, issuer, subject)` and persist only that digest. Treat static-token
mode as one deployment principal. Re-check the tool's required scopes on every
task method.

**Rationale**: OAuth access tokens can refresh, so binding to the token string
would break reconnects. Principal components remain stable across refreshes.
Returning `-32602` for ownership, scope, unknown, and expiry failures prevents
task-existence probing.

## Decision 5: Make cancellation protocol-reliable and execution-best-effort

**Decision**: Atomically transition a non-terminal task to `cancelled`, make
terminal states immutable, and cancel its in-process asyncio handle when
available.

**Rationale**: Some QMT calls run in synchronous threads or worker processes
and cannot be forcefully interrupted without risking shared state. The client
still receives deterministic cancellation semantics, while cooperative work
gets an immediate signal and late completion cannot overwrite cancellation.

## Decision 6: Keep qmtctl compatible by resolving tasks in transport

**Decision**: Advertise the Tasks extension in qmtctl wait/detach modes,
register custom Tasks methods with the official Go SDK, and wrap its HTTP
transport to recognize a task response. Default wait mode polls and rewrites
the final response to the original tool result; detach exposes the handle;
sync omits the extension.

**Rationale**: Go SDK 1.7.0 supports extension negotiation and custom methods
but does not yet decode Tasks tool-call result variants. A bounded transport
adapter preserves official SDK lifecycle/auth behavior and avoids changing
every existing qmtctl business command.

## Decision 7: Separate request timeout from task timeout

**Decision**: Keep `--timeout` as the limit for one HTTP exchange and add
`--task-timeout` for the complete polling lifecycle.

**Rationale**: Applying the existing HTTP client timeout to the entire poll
loop would cancel healthy long-running tasks. Each poll must remain bounded,
and OAuth authorization must be applied afresh so long tasks can survive token
refresh.

## Decision 8: Split later extension features cleanly

**Decision**: 023 supports lifecycle and the stable `input_required` envelope
needed for basic dispatch, but defers multi-round structured elicitation to 024
and status subscriptions/notifications to 025.

**Rationale**: Official conformance treats these as composable surfaces. A
small lifecycle foundation makes persistence, auth, and CLI behavior testable
before adding client-originated input and push delivery.

## Primary Sources

- MCP versioning and stable revision:
  https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning
- MCP Tasks overview:
  https://modelcontextprotocol.io/extensions/tasks/overview
- SEP-2663 Tasks final specification:
  https://modelcontextprotocol.io/seps/2663-tasks-extension
- Tasks extension draft repository:
  https://github.com/modelcontextprotocol/ext-tasks
- Official Python SDK v2.0.0:
  https://github.com/modelcontextprotocol/python-sdk/tree/v2.0.0
- Official Go SDK v1.7.0:
  https://github.com/modelcontextprotocol/go-sdk/tree/v1.7.0
- Official MCP conformance:
  https://github.com/modelcontextprotocol/conformance
