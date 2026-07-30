# Feature Specification: MCP Protocol Foundation

**Feature Branch**: `codex/019-mcp-protocol-foundation`

**Created**: 2026-07-31

**Status**: Approved

**Depends on**: 002 (MCP core), 007 (qmtctl), 008 (CI foundation),
011 (release pipeline).

## Summary

Make MCP 2026-07-28 the preferred production protocol while preserving the
2025-11-25, 2025-06-18, and 2025-03-26 compatibility path on the same endpoint.
Use the stable official Python and Go SDKs for dual-era behavior, test both eras
with the official conformance suite, and make both runtimes reproducible.

Structured tool metadata, full OAuth, Tasks, Apps, Resources, and MCP Registry
publication remain in later specs.

## User Scenarios & Testing

### User Story 1 - Modern stateless server with legacy compatibility (Priority: P1)

An MCP host can use the current stateless protocol, while an older host can keep
using the sessionful initialize flow at the same `/mcp` URL.

**Why this priority**: Modern hosts need `server/discover`, per-request metadata,
standard routing headers, cache hints, and no sticky session. Existing hosts
must not be broken during ecosystem adoption.

**Independent Test**: Run same-endpoint modern/legacy integration tests,
official 2026 tool-list/header/cache conformance, and legacy
initialize/ping/tool-list conformance against one no-broker server.

**Acceptance Scenarios**:

1. **Given** a 2026 client, **when** it calls `server/discover` and a tool,
   **then** each request is stateless, carries required metadata and HTTP
   headers, receives cache hints, and never receives an MCP session id.
2. **Given** a 2025 client, **when** it initializes and calls a tool, **then**
   the server negotiates the requested supported legacy revision, issues and
   honors a session id, and accepts the initialized notification.
3. **Given** a request whose modern headers and body disagree, **when** the
   server validates it, **then** it returns the standardized header-mismatch
   protocol error.

---

### User Story 2 - Modern-first qmtctl with automatic fallback (Priority: P1)

An operator uses one qmtctl binary against new or old MCP servers. qmtctl tries
the 2026 discovery path first and falls back to the legacy initialize flow only
when the server does not support modern discovery.

**Why this priority**: Tooling adoption will be uneven after a breaking protocol
release.

**Independent Test**: Run qmtctl against official modern and legacy client
conformance servers and verify the negotiated request era.

**Acceptance Scenarios**:

1. **Given** a modern server, **when** qmtctl connects, **then** it uses
   `server/discover`, 2026 per-request metadata, `Mcp-Method`, `Mcp-Name`, and
   no session.
2. **Given** a legacy server, **when** modern discovery is unsupported, **then**
   qmtctl falls back to initialize, sends a valid initialized notification, and
   propagates the negotiated version and optional session id.
3. **Given** an unsupported or invalid response, **when** qmtctl connects,
   **then** it fails closed before presenting a successful tool result.

---

### User Story 3 - Protocol regressions blocked in CI (Priority: P1)

A maintainer receives a failing pull-request check when either modern or legacy
server/client behavior breaks.

**Why this priority**: Local application tests cannot independently prove wire
interoperability.

**Independent Test**: Run the pinned official MCP conformance runner against
the broker-neutral server and qmtctl conformance driver in both protocol eras.

**Acceptance Scenarios**:

1. **Given** the no-broker server, **when** CI runs selected 2026 and 2025
   scenarios, **then** all pass without an expected-failure baseline.
2. **Given** the qmtctl driver, **when** CI runs modern metadata/header/tool-call
   and legacy initialize/tool-call scenarios, **then** all pass.
3. **Given** a conformance failure, **when** CI completes, **then** the job fails
   and preserves the runner output as evidence.

---

### User Story 4 - Reproducible MCP runtime (Priority: P1)

An image rebuild installs the same Python dependency graph rather than whatever
versions happen to be newest on the package index that day.

**Why this priority**: The MCP SDK controls wire behavior; an unreviewed upgrade
can break clients even when application source is unchanged.

**Independent Test**: Build clean Python 3.12 environments from the committed
lock on Linux and validate the lock for the Windows Python 3.12 target used
under Wine.

**Acceptance Scenarios**:

1. **Given** the committed dependency declaration and lock, **when** a clean
   environment installs it, **then** all direct and transitive versions are
   fixed and the official MCP package reports the reviewed version.
2. **Given** the appliance Dockerfile, **when** the dependency layer builds,
   **then** it installs from the lock rather than the floating declaration.
3. **Given** an application-only source change, **when** the image rebuilds,
   **then** the expensive pinned dependency layer remains cacheable.

### Edge Cases

- A server supports modern and legacy clients concurrently.
- A legacy server negotiates 2025-11-25, 2025-06-18, or 2025-03-26.
- `server/discover` is absent, returns method-not-found, or reports no mutually
  supported modern version.
- Streamable HTTP returns either JSON or an SSE response.
- Modern traffic accidentally receives a session id.
- Modern routing headers do not match the JSON-RPC body.
- The official conformance package publishes a newer release.
- A transitive dependency has platform-specific markers or wheels.

## Requirements

### Functional Requirements

- **FR-001**: The server MUST use stable official MCP Python SDK 2.x and serve
  the 2026-07-28 stateless era plus supported legacy handshake eras on the same
  `/mcp` endpoint.
- **FR-002**: Modern requests MUST implement `server/discover`, carry the 2026
  protocol/client metadata envelope, validate standard MCP HTTP headers, and
  remain sessionless.
- **FR-003**: Modern list responses MUST include non-negative `ttlMs` and an
  accurate private/public `cacheScope`.
- **FR-004**: Legacy requests MUST continue to negotiate 2025-11-25,
  2025-06-18, and 2025-03-26 through initialize and session semantics.
- **FR-005**: qmtctl MUST use stable official MCP Go SDK 1.7 or newer to prefer
  2026-07-28 and automatically fall back to the legacy initialize flow.
- **FR-006**: qmtctl MUST preserve static bearer-token behavior and JSON/SSE
  result compatibility across both eras.
- **FR-007**: The repository MUST include an isolated qmtctl conformance driver
  that exercises the production client implementation without becoming a
  user-facing qmtctl command.
- **FR-008**: CI MUST pin an official conformance runner that supports
  2026-07-28 and run selected modern caching, header, and tool-list scenarios
  plus legacy initialize, ping, and tool-list scenarios.
- **FR-009**: CI MUST run modern metadata/header/tool-call and legacy
  initialize/tool-call scenarios against qmtctl.
- **FR-010**: Conformance checks MUST NOT add test-only tools, resources, prompts,
  sampling, logging, or elicitation capabilities to the production server.
- **FR-011**: Runtime direct dependencies and the complete transitive graph MUST
  be pinned in a committed Python 3.12 lock.
- **FR-012**: The Dockerfile MUST install the committed lock before copying
  frequently changing application source.
- **FR-013**: CI MUST install and run the official SDK integration test tier using the
  committed runtime lock.
- **FR-014**: The qmtctl Go module and CI/release toolchain MUST pin the Go
  version required by the stable official SDK.
- **FR-015**: Documentation MUST identify 2026-07-28 as preferred and document
  the supported compatibility revisions and conformance commands.
- **FR-016**: No broker pack, xtquant installation, QMT login, token, or NAS
  access MUST be required for protocol conformance.
- **FR-017**: PR and main CI MUST build and smoke the complete linux/amd64
  appliance before release, export a reusable build cache, and let release
  consume that tested cache.

## Key Entities

- **Protocol Era**: Modern stateless 2026-07-28 or a negotiated legacy
  initialize/session revision.
- **Runtime Lock**: Fully resolved Python 3.12 dependency graph consumed by CI
  and the image build.
- **Conformance Driver**: Test-only executable that translates official client
  scenarios into calls through the production qmtctl client.

## Success Criteria

- **SC-001**: Official server conformance passes every selected universal 2026
  and 2025 scenario without an expected-failure baseline.
- **SC-002**: Official qmtctl client conformance passes every selected modern
  and legacy scenario.
- **SC-003**: Integration tests prove modern discovery/stateless/header/cache
  behavior and legacy negotiation/session behavior at one endpoint.
- **SC-004**: A clean Python 3.12 environment installs the lock and passes all
  host integration tests.
- **SC-005**: Existing Python unit tests and qmtctl tests, vet, and build all
  remain green.
- **SC-006**: Docker dependency installation no longer consumes unpinned
  requirements.
- **SC-007**: The native linux/amd64 CI image build passes before merge and its
  cache is reusable by the release workflow.

## Out of Scope

- Tool output schemas, annotations, profiles, and dynamic visibility (020).
- JWT/JWKS validation and interactive OAuth flows (021).
- MCP Tasks (023), MCP Apps (024), Resources and Registry publication (025).
- Live xtdata/xttrade validation.

## Assumptions

- 2026-07-28 is the latest stable MCP release while this feature lands.
- Official MCP Python SDK 2.0.0 and Go SDK 1.7.0 are the stable implementation
  baselines; FastMCP 3.4.5 remains on Python SDK 1.29.0 and is replaced.
- The conformance runner's application-specific fixture scenarios are not
  universal server requirements and are intentionally excluded.
