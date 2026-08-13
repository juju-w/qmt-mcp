# Feature Specification: MCP 2026-07-28 Only

**Feature Branch**: `codex/029-modern-only-mcp`

**Created**: 2026-08-14

**Status**: Approved

**Input**: Ship QMT-MCP 1.0.0 on the latest stable MCP 2026-07-28 protocol only;
do not retain older MCP protocol compatibility.

**Depends on**: 019 (protocol foundation), 021 (OAuth), 023-025 (Tasks).

## Summary

Make MCP `2026-07-28` the sole protocol revision supported by the QMT-MCP
server and qmtctl. Remove the legacy initialize/session lifecycle and the legacy
HTTP+SSE transport, require stateless Streamable HTTP, and publish the change as
the breaking QMT-MCP `1.0.0` release.

MCP Apps and market-data visualizations are intentionally a follow-on feature;
this feature establishes the modern extension-capable protocol baseline they
need.

## User Scenarios & Testing

### User Story 1 - Stateless modern MCP endpoint (Priority: P1)

A current MCP host connects to QMT-MCP and every operation is an independent,
self-describing `2026-07-28` request.

**Why this priority**: One protocol era removes hidden session state and makes
the public contract unambiguous before the 1.0 release.

**Independent Test**: Run official modern server conformance and direct ASGI
requests for discovery, tool listing, tool calls, Tasks, and subscriptions.

**Acceptance Scenarios**:

1. **Given** a valid modern request, **when** it reaches `/mcp`, **then** it is
   served without `initialize`, `notifications/initialized`, or
   `Mcp-Session-Id`.
2. **Given** multiple requests from one client, **when** they reach different
   server instances, **then** no protocol session affinity is required.
3. **Given** `server/discover`, **when** the server responds, **then** its only
   supported protocol revision is `2026-07-28`.

---

### User Story 2 - Old clients fail clearly (Priority: P1)

An operator using a 2025-era client gets a deterministic unsupported-protocol
error instead of a partial connection, session, or ambiguous HTTP failure.

**Why this priority**: A deliberate compatibility break must be observable and
actionable rather than silently misbehaving.

**Independent Test**: Send legacy initialize, missing-version, wrong-version,
standalone GET, and DELETE requests and assert that none establishes a session.

**Acceptance Scenarios**:

1. **Given** an `initialize` request for a 2025 revision, **when** it reaches
   `/mcp`, **then** the server rejects it with the standard unsupported protocol
   error and advertises only `2026-07-28`.
2. **Given** a POST without the modern protocol header, **when** it reaches
   `/mcp`, **then** the server rejects it without invoking a tool.
3. **Given** any rejected legacy request, **when** the response is inspected,
   **then** it contains no `Mcp-Session-Id` header.

---

### User Story 3 - Modern-only qmtctl (Priority: P1)

An operator uses qmtctl against a 1.0 server and knows the CLI will never
continue over a downgraded protocol.

**Why this priority**: The bundled CLI is the project's reference client and
must enforce the same contract as the server.

**Independent Test**: Run qmtctl against modern and legacy fixture servers and
verify that only the modern server reaches tool listing or tool invocation.

**Acceptance Scenarios**:

1. **Given** a `2026-07-28` server, **when** qmtctl connects, **then** discovery,
   list, call, Tasks, and notification operations work normally.
2. **Given** a server that offers only a legacy initialize lifecycle, **when**
   qmtctl connects, **then** qmtctl returns a protocol error and does not invoke
   a business tool.
3. **Given** a modern discovery failure, **when** qmtctl handles it, **then** it
   does not report a successful legacy connection.

---

### User Story 4 - Honest 1.0 release and migration path (Priority: P1)

A user reading the release and deployment documentation can tell which clients
work, why an older client fails, and how to upgrade.

**Why this priority**: Protocol compatibility is part of the public product
contract, not an internal implementation detail.

**Independent Test**: Inspect generated release notes, README, client guide,
deployment skill, and CI commands for stale legacy compatibility claims.

**Acceptance Scenarios**:

1. **Given** the breaking commit lands on main, **when** release automation
   resolves the next version, **then** it publishes `1.0.0`.
2. **Given** a user follows current setup documentation, **when** they configure
   a client, **then** they are directed to a `2026-07-28`-capable Streamable HTTP
   host.
3. **Given** a user upgrades from 0.x, **when** they read the migration note,
   **then** removal of initialize/session and legacy SSE support is explicit.

### Edge Cases

- The request has `MCP-Protocol-Version: 2026-07-28` but mismatched body metadata.
- The request uses a future or malformed protocol revision.
- The request is a batch or malformed JSON document and has no usable request id.
- Authentication fails before protocol validation.
- OAuth discovery and health endpoints are not MCP RPC requests.
- A reverse proxy strips the modern routing or protocol headers.
- qmtctl's upstream SDK attempts automatic legacy fallback internally.
- Tasks and Apps extensions are advertised only through the modern capability map.

## Requirements

### Functional Requirements

- **FR-001**: `/mcp` MUST accept only MCP `2026-07-28` requests.
- **FR-002**: The server MUST run Streamable HTTP in stateless mode and MUST NOT
  issue or require `Mcp-Session-Id`.
- **FR-003**: The server MUST implement `server/discover` and advertise only
  `2026-07-28`.
- **FR-004**: Legacy initialize requests and requests missing a valid modern
  protocol declaration MUST fail with a structured unsupported-protocol error.
- **FR-005**: Protocol rejection MUST occur before tool dispatch and MUST retain
  the request id when a bounded valid JSON-RPC request can be decoded.
- **FR-006**: `/livez`, `/healthz`, and OAuth metadata endpoints MUST remain
  available under their existing authentication and disclosure rules.
- **FR-007**: The legacy HTTP+SSE MCP transport MUST no longer be selectable;
  the existing `http` spelling MAY remain as a deprecated alias for
  Streamable HTTP.
- **FR-008**: qmtctl MUST require a negotiated protocol revision of exactly
  `2026-07-28` and MUST fail closed before business tool calls on older servers.
- **FR-009**: qmtctl's MCP HTTP transport MUST refuse requests that do not carry
  the modern protocol revision, preventing SDK fallback traffic from becoming
  a supported execution path.
- **FR-010**: CI MUST run only the official `2026-07-28` conformance scenarios
  plus explicit negative tests for legacy requests and clients.
- **FR-011**: Existing OAuth, pagination, gzip, Tasks, MRTR, and task
  subscriptions MUST continue to work on the modern path.
- **FR-012**: User-facing documentation and operational skills MUST remove
  claims of 2025 compatibility and document the 1.0 migration.
- **FR-013**: The release commit MUST use the repository's breaking-change
  convention so automated SemVer resolves `1.0.0`; source code MUST NOT
  manually edit `VERSION` or create the tag.
- **FR-014**: No broker pack, xtquant installation, QMT login, account, or
  trading permission MUST be required for protocol acceptance tests.

## Key Entities

- **Modern request envelope**: Protocol version, client identity, and client
  capabilities carried per request with standard routing headers.
- **Protocol rejection**: A bounded JSON-RPC error proving that no legacy
  lifecycle or tool execution occurred.
- **Modern-only client policy**: qmtctl transport enforcement plus negotiated
  version verification.

## Success Criteria

- **SC-001**: All selected official `2026-07-28` server and client conformance
  scenarios pass with no legacy scenarios in the acceptance matrix.
- **SC-002**: Legacy initialize, missing-version, and wrong-version tests have a
  100% structured rejection rate and create zero MCP sessions.
- **SC-003**: qmtctl performs zero business tool calls against a legacy-only
  fixture server.
- **SC-004**: The modern OAuth, Tasks, MRTR, notification, pagination, and gzip
  integration suites remain green.
- **SC-005**: Repository search finds no current compatibility claim that says
  QMT-MCP 1.0 supports a 2025 MCP protocol revision.
- **SC-006**: Main CI and the subsequent `1.0.0` release workflow complete
  successfully.

## Out of Scope

- Supporting a future MCP revision automatically.
- Maintaining a second endpoint for legacy clients.
- MCP Apps UI resources or K-line rendering (feature 030).
- Changing tool names, tool schemas, QMT data behavior, or trading permissions.

## Assumptions

- MCP `2026-07-28` remains the latest stable core revision for this release.
- Official Python SDK `2.0.0` and Go SDK `1.7.0` remain the reviewed stable
  baselines.
- Users choosing QMT-MCP 1.0 accept upgrading their MCP host/client.
