# Feature Specification: Production MCP Server Core

**Feature Branch**: `002-mcp-server-core`

**Created**: 2026-06-03

**Status**: Draft

**Input**: User description: "Turn the vendored read-only MCP prototype into a production-grade MCP server core. It should expose one guarded MCP SSE service, load the resolved broker-pack runtime config from 001, enforce bearer-token auth, provide a stable health contract, register tools through explicit structured contracts, run blocking QMT/xtquant operations without stalling the server, and emit structured/audit logs. Market-data tools, account-query tools, and readiness supervision are separate follow-on features."

## Clarifications

### Session 2026-06-03

- **Q1 - Current permission reality**: The first usable MCP capability is expected
  to be `xtdata` market data. `xttrade` account-query/trading permission appears
  unavailable in the current broker environment, but `xttrade` read-only account
  query support is still required for permissioned users. Until permission is
  proven, account-query tools must be disabled or reported as not authorized.
- **Q2 - Tool design posture**: MCP tools must be designed from official XtQuant
  API behavior, not copied as raw SDK pass-through. The server core owns
  capability gating and tool-contract rules; feature 003 owns the `xtdata` tool
  catalog; feature 004 owns planned read-only `xttrade` account queries.
- **Q3 - Persistence posture**: Postgres is not required for the 002/003 MVP.
  Audit records default to an append-only JSONL sink; Postgres may be added later
  as an optional persistence/observability feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent Connects To A Guarded MCP Endpoint (Priority: P1)

An operator starts the appliance with a broker pack mounted and a deployment token
configured. An AI agent connects to the MCP endpoint, authenticates with the
token, and can discover the server's registered tool contracts. Requests without
the token are rejected. The endpoint is available as a server surface even if QMT
has not yet been manually logged in.

**Why this priority**: Without a guarded, discoverable MCP endpoint there is no
safe agent integration point. This is the MVP foundation for all later tool
features.

**Independent Test**: Start the appliance with a valid token and no QMT login.
Confirm unauthenticated MCP/HTTP requests are rejected, authenticated discovery
succeeds, and the health surface reports the server is live while QMT-dependent
capabilities are not yet ready or not yet implemented.

**Acceptance Scenarios**:

1. **Given** the MCP server is running with a configured token, **When** a client connects without `Authorization: Bearer <token>`, **Then** the request is rejected and no tool metadata is returned.
2. **Given** the MCP server is running with a configured token, **When** a client connects with the correct bearer token and lists tools, **Then** it receives only explicitly registered tools with structured schemas.
3. **Given** QMT has not yet been manually logged in, **When** an authenticated client checks health, **Then** the server reports itself live and reports QMT-dependent capability state as not ready, unavailable, or delegated to later readiness supervision rather than failing the whole endpoint.

---

### User Story 2 - Operator Observes Health And Auditability (Priority: P2)

An operator or orchestration layer needs to know whether the MCP service itself is
alive and whether QMT-related dependencies are ready. The operator also needs a
durable record of agent actions for diagnosis and safety review.

**Why this priority**: The appliance is trading-adjacent. Even read-only actions
need clear observability, and orchestration needs a health contract that later
features can enrich.

**Independent Test**: Run authenticated health checks and sample tool calls.
Confirm health responses use a stable structured shape, tool calls produce audit
records, and logs omit tokens, credentials, and full secret-bearing arguments.

**Acceptance Scenarios**:

1. **Given** the server is running, **When** an authenticated client calls the health surface, **Then** it receives liveness plus named dependency states for broker config, xtdata, trader, and account subscriptions.
2. **Given** a tool call is accepted by the server, **When** it completes or fails, **Then** an audit record is written with timestamp, tool name, account identifier if applicable, sanitized argument summary, outcome, and error type if any.
3. **Given** logs are inspected, **When** token or credential-like values were present in the environment or request headers, **Then** those secrets do not appear in structured logs or audit records.

---

### User Story 3 - Server Remains Responsive During Slow QMT Work (Priority: P2)

An agent may call tools whose underlying QMT/xtquant operation is slow or
blocking. Other clients and health checks must remain responsive while that work
runs.

**Why this priority**: QMT/xtquant calls are not guaranteed to be async-friendly.
The core must prevent one slow broker operation from wedging the whole MCP
surface.

**Independent Test**: Use a deliberately slow or simulated blocking tool
registered through the core. While it runs, make authenticated health and tool
discovery calls and confirm they respond within the expected latency budget.

**Acceptance Scenarios**:

1. **Given** a slow QMT-backed tool is running, **When** another authenticated client calls health, **Then** health responds without waiting for the slow tool to finish.
2. **Given** several slow calls are in progress, **When** the concurrency limit is reached, **Then** additional calls are queued or rejected with a clear capacity error rather than exhausting the process.
3. **Given** a blocking operation raises an exception, **When** the tool response is returned, **Then** the client receives a uniform error envelope and no stack trace.

### Edge Cases

- `QMT_MCP_TOKEN` is missing or empty while the endpoint is bound to a non-loopback interface -> startup fails closed or refuses external service exposure with a clear message.
- `QMT_MCP_TOKEN` is missing while explicitly bound to loopback for local development -> allowed only if clearly logged as local-only and unauthenticated.
- Resolved broker config from 001 is missing or malformed -> MCP does not guess paths; health reports config failure and QMT-dependent tools remain unavailable.
- `mcp.mode: trade` is present before trading guardrails exist -> write/trade tools are still not exposed; read-only remains the effective surface.
- A tool implementation returns non-JSON-serializable objects -> the core converts through declared output models or returns a serialization error envelope.
- A tool call includes sensitive-looking fields -> audit logging records a sanitized summary rather than full raw arguments.
- The audit log path is unwritable -> startup fails closed or health reports degraded according to the final plan; calls must not silently proceed without audit.
- Optional database configuration is present but unreachable -> MCP core falls back only if explicitly configured to do so; otherwise health reports persistence degraded and audit guarantees remain explicit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The MCP server MUST expose a single authenticated MCP SSE endpoint for agent connections.
- **FR-002**: The server MUST require bearer-token authentication on all externally reachable MCP and HTTP surfaces.
- **FR-003**: The server MUST load the resolved broker runtime configuration produced by feature 001, including broker identity, xtquant path, userdata path, and MCP mode.
- **FR-004**: The server MUST default to read-only behavior. It MUST NOT expose order, cancel, transfer, borrow, export, or other write-capable tools in this feature.
- **FR-005**: The server MUST provide a tool-registration framework where every exposed tool has explicit input validation, structured output, accurate descriptions, and named enums where bounded choices exist.
- **FR-006**: The server MUST expose only an allow-listed tool surface. Dependency-provided tools MUST NOT become visible merely because a package was imported.
- **FR-006a**: The server MUST report tool-family capability states separately for core, market-data, account-query, and future trading families.
- **FR-007**: The server MUST run blocking QMT/xtquant operations in controlled worker execution so the MCP event loop and health surface remain responsive.
- **FR-008**: The server MUST enforce a configurable concurrency limit for worker-backed operations and return a clear capacity error when the limit is exceeded.
- **FR-009**: The server MUST provide a stable health response containing liveness, broker-config state, and named placeholders/states for xtdata, trader, and account subscription readiness.
- **FR-010**: The server MUST emit structured runtime logs without leaking bearer tokens, credentials, or raw secret-bearing request data.
- **FR-011**: The server MUST append an audit record for every accepted tool invocation, including timestamp, tool name, account identifier when applicable, sanitized argument summary, outcome, latency, and error type.
- **FR-011a**: The default audit sink MUST be append-only JSONL. Database-backed audit storage MAY be added later but MUST NOT be required for this feature.
- **FR-012**: The server MUST return uniform client-facing error envelopes for validation failures, authentication failures, readiness failures, capacity limits, dependency failures, and unexpected internal failures.
- **FR-013**: The server MUST hide internal stack traces and implementation details from clients while preserving enough structured log detail for operator diagnosis.
- **FR-014**: The server MUST treat `mcp.mode: trade` as a future capability flag only; until trading guardrails are delivered by a later feature, the effective exposed surface remains read-only.
- **FR-015**: The server MUST be independently testable without a logged-in QMT session by using health, authentication, discovery, and at least one non-trading/simulated tool path.
- **FR-016**: The server MUST support disabling an entire tool family with a clear reason, such as `not_authorized` for `xttrade` when broker/account permission is unavailable.

### Key Entities *(include if feature involves data)*

- **MCP Server Core**: The authenticated agent-facing service that owns lifecycle, routing, tool registration, error shaping, worker execution, health reporting, and audit logging.
- **Resolved Broker Runtime Config**: The effective configuration produced by feature 001 and consumed by the MCP core; includes broker identity, paths, and MCP mode, but no secrets.
- **Tool Contract**: The explicit schema and metadata for a registered MCP tool: name, description, input model, output model, allowed errors, readiness requirements, and audit policy.
- **Tool Family Capability State**: The observable enabled/disabled/not-ready/not-authorized state for a grouped capability such as core, xtdata, xttrade query, or future trading tools.
- **Health State**: A structured snapshot of server liveness and dependency state, including broker config, xtdata, trader, and account subscriptions.
- **Audit Record**: An append-only event describing one accepted tool invocation and its outcome, sanitized for secrets.
- **Audit Sink**: The persistence target for audit records. The default sink is JSONL; database sinks are optional future extensions.
- **Error Envelope**: The uniform client-facing failure structure used across all tools and HTTP/MCP surfaces.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of unauthenticated requests to externally reachable MCP/HTTP surfaces are rejected.
- **SC-002**: An authenticated client can discover the registered tool contracts before QMT login, with no write-capable tools present.
- **SC-003**: Health checks remain responsive while at least one simulated blocking tool call is running.
- **SC-004**: 100% of accepted tool invocations produce an audit record with no bearer token or credential leakage.
- **SC-005**: Client-facing failures use the uniform error envelope for validation, readiness, capacity, and dependency errors.
- **SC-006**: Importing or mounting a dependency package cannot expose an unallow-listed tool.

## Assumptions

- Feature 001 already resolves the broker pack and writes the runtime config consumed by the MCP server.
- Market-data tools are delivered by feature 003, account-query tools by feature 004, and process/readiness supervision by feature 005.
- Manual QMT login remains outside this feature. The core defines health fields and readiness-aware error semantics but does not itself guarantee QMT login detection or trader auto-connect.
- The current operator environment is xtdata-first. `xttrade` query tools remain
  a planned feature, but local successful-path validation is blocked until broker
  permission is explicitly available.
- Trading/write tools and their guardrails are out of scope for this feature even if `mcp.mode: trade` appears in broker config.
- Postgres is not part of the 002/003 MVP. A later persistence feature may add
  Postgres for audit search, task state, or market-data warehousing.
- TLS termination and remote network hardening beyond bearer-token auth are handled by deployment features.
