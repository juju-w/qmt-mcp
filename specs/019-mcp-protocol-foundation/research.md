# Research: MCP Protocol Foundation

## Decision 1: Production protocol baseline

**Decision**: Prefer MCP `2026-07-28` and preserve the legacy `2025-11-25`,
`2025-06-18`, and `2025-03-26` flows on one endpoint.

**Evidence**:

- The official release API records 2026-07-28 as stable, non-prerelease,
  published on 2026-07-28.
- Modern MCP removes initialize and session ids. It uses `server/discover`,
  per-request metadata, standard routing headers, and cache hints.
- Official SDKs provide modern-first probing and legacy fallback.

**Rejected alternatives**:

- Keeping 2025-11-25 as primary: would ship a legacy architecture after the
  stable stateless release.
- Dropping legacy support: would break hosts whose MCP libraries have not yet
  upgraded.

## Decision 2: Server SDK

**Decision**: Replace third-party FastMCP with official MCP Python SDK 2.0.0 and
its `MCPServer`.

**Evidence**:

- Official Python SDK 2.0.0 is the stable v2 release and supports 2026-07-28 and
  every earlier revision.
- Its Streamable HTTP manager routes 2026 requests through a stateless
  per-request path and legacy requests through sessionful initialization on the
  same ASGI application.
- FastMCP 3.4.5 requires MCP Python SDK 1.29.0 and downgrades an environment
  containing SDK 2.0.0, so it cannot be the modern protocol foundation.

**Rejected alternatives**:

- A custom ASGI 2026 protocol implementation: duplicates version routing,
  metadata, header, cache, and error handling already maintained by the official
  SDK.
- Waiting for FastMCP: makes a third-party release schedule block the stable
  protocol.

## Decision 3: qmtctl SDK

**Decision**: Use official MCP Go SDK 1.7.0 and Go 1.25 for MCP calls while
retaining qmtctl's health/discovery formatting and static bearer-token behavior.

**Evidence**:

- Go SDK 1.7.0 enables 2026-07-28 by default, probes `server/discover`, and
  automatically falls back to the legacy initialize flow.
- It validates modern standard headers and handles sessionful legacy transports.
- The SDK requires Go 1.25, so development, CI, and release builders must move
  together.

**Rejected alternative**: Extending the handwritten JSON-RPC transport would
duplicate protocol negotiation, MRTR, modern headers, caching, and fallback.

## Decision 4: Conformance scope

**Decision**: Pin official conformance `0.2.0-alpha.10`, currently the published
runner containing 2026 scenarios. Run selected universal modern and legacy
scenarios against the server and qmtctl.

**Evidence**:

- Stable conformance 0.1.16 predates the 2026 scenarios.
- The alpha runner includes `server-stateless`, caching, HTTP header validation,
  request metadata, and modern client header scenarios.
- `server-stateless` also requires a production tool named
  `test_missing_capability`; it is therefore excluded from the committed
  universal selection. Same-endpoint integration tests cover discovery,
  sessionlessness, and legacy sessions without widening the production tools.
- Other server scenarios require named fixture tools and optional capabilities
  such as resources, prompts, sampling, elicitation, audio, or image content.

**Rejected alternatives**:

- Running the full server suite with an expected-failure baseline: the baseline
  would mostly describe intentionally absent optional features and could conceal
  real regressions.
- Adding conformance fixture tools to production: violates the explicit
  allow-listed tool surface.

## Decision 5: qmtctl conformance adapter

**Decision**: Add a test-only Go executable under `cmd/conformance`, importing
the production internal qmtctl client. It reads `MCP_CONFORMANCE_SCENARIO` and
the server URL appended by the runner.

**Rationale**: The official runner controls the test server and process
lifecycle. Keeping the adapter outside the root qmtctl command prevents a
testing interface from becoming part of the distributed CLI.

## Decision 6: CI topology

**Decision**:

- Keep the dependency-light Python unit job.
- Add a protocol-conformance job that installs the runtime lock, runs integration
  tests, starts a minimal loopback/no-auth/no-xtdata server, and invokes the
  pinned conformance package.
- Build the qmtctl conformance driver once and run both client scenarios.

**Rationale**: The job is broker-neutral and verifies the same Python dependency
graph used by the appliance.

## Primary Sources

- MCP releases:
  https://github.com/modelcontextprotocol/modelcontextprotocol/releases
- MCP 2026-07-28 lifecycle and schema:
  https://modelcontextprotocol.io/specification/2026-07-28
- MCP Streamable HTTP transport:
  https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- Official conformance framework:
  https://github.com/modelcontextprotocol/conformance
- Official MCP Python SDK:
  https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0
- Official MCP Go SDK:
  https://github.com/modelcontextprotocol/go-sdk/releases/tag/v1.7.0
