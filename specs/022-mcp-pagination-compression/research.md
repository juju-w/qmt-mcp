# Research: MCP Pagination and HTTP Compression

## Decision 1: Paginate the authorized tool view

**Decision**: Override the official Python SDK's high-level
`tools/list` handler, call its existing request-scoped `list_tools`, then
paginate the filtered result.

**Rationale**: MCP pagination is defined for `tools/list`, but MCP Python SDK
2.0.0's `MCPServer._handle_list_tools` currently returns every registered tool.
The application already subclasses `MCPServer` for OAuth visibility, making
the handler the narrowest compatible extension point.

## Decision 2: Use keyset cursors bound to a view fingerprint

**Decision**: Sort by unique tool name. Encode a bounded, URL-safe, versioned
cursor containing the last tool name and a truncated SHA-256 fingerprint of
the complete visible name sequence.

**Rationale**: Offset cursors silently shift when profiles or OAuth scopes
change. Binding the cursor to the visible view fails closed and prevents one
principal's cursor from resuming a different catalog. The token need not be
secret or signed because it grants no authority and every decoded field is
validated against the current authorized view.

## Decision 3: Bound qmtctl aggregation beyond the SDK default

**Decision**: Use official Go SDK `ListTools` calls while adding a qmtctl loop
that tracks seen cursors and tool names and caps traversal at 1000 pages.

**Rationale**: Go SDK 1.7.0 provides a pagination iterator but does not detect
cursor cycles. A remote server must not be able to keep qmtctl in an unbounded
loop or amplify memory with duplicate pages.

## Decision 4: Use Starlette's gzip middleware

**Decision**: Wrap the official MCP transport application with the Starlette
1.3.1 `GZipMiddleware`, using compression level 6 and a configurable minimum
size.

**Rationale**: Starlette is already a pinned MCP SDK dependency. Its responder
handles negotiation, `Vary`, length updates, existing encodings, and explicitly
excludes `text/event-stream`. A custom compressor would duplicate subtle HTTP
behavior.

## Decision 5: Let Go's standard transport decode gzip

**Decision**: Do not set `Accept-Encoding` manually in qmtctl. Keep the default
Go transport underneath the bearer wrapper.

**Rationale**: Go's standard transport automatically advertises and decodes
gzip only when the caller did not manually set the header. Explicitly setting
it would disable transparent decompression.

## Primary Sources

- MCP 2026-07-28 pagination:
  https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination
- MCP 2026-07-28 Streamable HTTP:
  https://modelcontextprotocol.io/specification/2026-07-28/basic/transports
- Official Python SDK v2.0.0:
  https://github.com/modelcontextprotocol/python-sdk/tree/v2.0.0
- Official Go SDK v1.7.0:
  https://github.com/modelcontextprotocol/go-sdk/tree/v1.7.0
- Starlette gzip middleware:
  https://www.starlette.io/middleware/#gzipmiddleware
