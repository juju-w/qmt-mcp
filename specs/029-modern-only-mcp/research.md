# Research: MCP 2026-07-28 Only

## Decision 1: Make the protocol break explicit

**Decision**: QMT-MCP 1.0 supports only core MCP `2026-07-28`.

**Evidence**:

- The MCP project published `2026-07-28` as a stable release on 2026-07-28.
- It removes initialize/initialized and protocol sessions, replacing them with
  `server/discover` and a self-describing `_meta` envelope on every request.
- All Tier 1 SDKs support the revision.
- QMT-MCP is still pre-1.0, making this the least costly point to remove the
  compatibility surface.

**Rejected alternative**: Continue modern-first dual-era support. This retains
session lifecycle, GET/DELETE behavior, fallback tests, and ambiguous support
expectations solely for clients the project no longer wants to target.

## Decision 2: Enforce modern-only before dispatch

**Decision**: Run the official Python server in stateless mode and add a small
ASGI protocol gate in front of the MCP application.

**Evidence**:

- `stateless_http=True` removes server-side session tracking but the Python SDK
  intentionally retains legacy compatibility on the same endpoint.
- Therefore the flag alone does not satisfy a modern-only product contract.
- A path-scoped gate can reject missing, old, malformed, or future protocol
  headers before the SDK creates a legacy connection or dispatches a tool.
- Health and OAuth metadata routes remain outside the gate.

**Rejected alternative**: Fork or patch the official SDK's internal supported
version list. That couples QMT-MCP to private SDK internals and makes security
updates harder.

## Decision 3: Refuse qmtctl fallback at the transport boundary

**Decision**: Keep the official Go SDK, wrap its MCP HTTP transport with a
modern-only policy, and verify the negotiated session revision.

**Evidence**:

- Go SDK 1.7.0 performs modern discovery and automatically falls back to
  initialize, with no public pin option.
- A transport wrapper can allow requests carrying exactly
  `Mcp-Protocol-Version: 2026-07-28` and reject fallback traffic locally.
- A post-connect negotiated-version check remains defense in depth.

**Rejected alternatives**:

- Reimplement discovery and tool calls manually: duplicates official protocol,
  OAuth, MRTR, Tasks, and error behavior.
- Allow fallback and reject only after initialize: technically fails closed but
  still performs a lifecycle the 1.0 client promises not to use.

## Decision 4: Remove legacy SSE selection

**Decision**: Accept `streamable-http` and the existing `http` alias, but reject
`sse` in runtime configuration.

**Evidence**:

- The legacy HTTP+SSE transport is deprecated in the 2026-07-28 release.
- The project already made Streamable HTTP its documented default.
- Keeping the `http` alias does not add another wire protocol; it resolves to
  the same stateless Streamable HTTP application.

## Decision 5: Reserve MCP Apps for feature 030

**Decision**: Do not add UI resources in this breaking protocol feature.

**Evidence**:

- MCP Apps is an independently versioned stable extension
  (`io.modelcontextprotocol/ui`, stable extension revision `2026-01-26`).
- The official Python SDK 2.0.0 includes an `Apps` extension implementation.
- Apps require a product/UI contract, static resource packaging, host capability
  negotiation, graceful text fallback, and visual testing.
- A read-only K-line App is the best first slice because QMT-MCP already has a
  mature bars tool and no trading permission is involved.

## Primary Sources

- MCP 2026-07-28 release:
  https://blog.modelcontextprotocol.io/posts/2026-07-28/
- MCP 2026-07-28 specification:
  https://modelcontextprotocol.io/specification/2026-07-28
- MCP Python SDK v2 protocol and stateless server documentation:
  https://py.sdk.modelcontextprotocol.io/
- MCP Go SDK protocol documentation:
  https://github.com/modelcontextprotocol/go-sdk/blob/main/docs/protocol.md
- MCP Apps overview and stable extension specification:
  https://modelcontextprotocol.io/extensions/apps/overview
  https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx
