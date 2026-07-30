# Feature Specification: MCP Pagination and HTTP Compression

**Feature Branch**: `codex/022-mcp-pagination-compression`

**Created**: 2026-07-31

**Status**: Approved

**Depends on**: 019 (MCP protocol foundation), 020 (tool contracts and
profiles), 021 (OAuth authorization).

## Summary

Paginate the MCP `tools/list` catalog with stable opaque cursors and make
qmtctl consume every page automatically. Pagination applies after startup
profile and per-request OAuth filtering so a cursor cannot reveal or resume a
different tool view.

Add negotiated gzip compression to non-streaming MCP HTTP responses. Keep SSE
uncompressed, preserve static and OAuth authentication, and retain the same
endpoint for preferred MCP `2026-07-28` and supported 2025 clients.

This feature does not change tool-call payloads or replace business-level
`limit` arguments used by market-data tools.

## User Scenarios & Testing

### User Story 1 - Hosts page through a large tool catalog (Priority: P1)

An MCP host lists a bounded page of authorized tools and follows `nextCursor`
until the catalog is exhausted.

**Independent Test**: Start the broker-neutral server with a page size of one
and list the two core tools through both modern and legacy sessions.

**Acceptance Scenarios**:

1. **Given** more visible tools than the configured page size, **when**
   `tools/list` is called without a cursor, **then** the server returns a
   deterministic first page and a non-empty opaque `nextCursor`.
2. **Given** the returned cursor, **when** `tools/list` is called again, **then**
   the server returns the next non-overlapping page and omits `nextCursor` on
   the final page.
3. **Given** a malformed, stale, or different-visibility cursor, **when** it is
   submitted, **then** the server returns JSON-RPC Invalid Params (`-32602`)
   without exposing cursor internals.
4. **Given** the same visible catalog, **when** pagination is repeated, **then**
   pages are ordered stably by tool name and produce the same traversal.

---

### User Story 2 - qmtctl always presents the complete catalog (Priority: P1)

An operator runs `qmtctl tools` and sees all authorized tools even when the
server splits the catalog across many pages.

**Independent Test**: Run qmtctl against a fixture returning three pages and
assert that it sends each cursor and renders every tool once.

**Acceptance Scenarios**:

1. **Given** a paginated modern or legacy server, **when** qmtctl lists tools,
   **then** it follows every emitted cursor and combines the pages.
2. **Given** a server that repeats a cursor or never terminates, **when**
   qmtctl lists tools, **then** it stops with a protocol error rather than
   looping indefinitely.
3. **Given** an unpaginated server, **when** qmtctl lists tools, **then**
   existing output remains unchanged.

---

### User Story 3 - Remote clients use smaller HTTP responses (Priority: P1)

A remote client that advertises gzip receives a compressed JSON MCP response,
while clients that do not advertise it and SSE streams remain unchanged.

**Independent Test**: Request a full tool page with and without
`Accept-Encoding: gzip`, decode the compressed response, and exercise an SSE
response with gzip advertised.

**Acceptance Scenarios**:

1. **Given** a JSON response above the configured threshold and a client that
   accepts gzip, **when** the response is sent, **then** it carries
   `Content-Encoding: gzip`, `Vary: Accept-Encoding`, and decodes to the same
   JSON document.
2. **Given** a client that does not advertise gzip or a response below the
   threshold, **when** the response is sent, **then** it is not compressed.
3. **Given** an SSE response, **when** the client advertises gzip, **then** the
   stream remains uncompressed and can be consumed incrementally.
4. **Given** qmtctl's standard HTTP transport, **when** the server returns
   gzip, **then** qmtctl transparently decodes it while traversing all pages.

---

### User Story 4 - Existing deployments upgrade without behavior drift (Priority: P1)

An existing static-token, OAuth, or reduced-profile deployment upgrades and
keeps the same authorized tool surface and protocol compatibility.

**Independent Test**: Re-run profile, OAuth scope, modern, legacy, conformance,
CLI, and image gates with pagination and compression enabled by default.

**Acceptance Scenarios**:

1. **Given** startup profile and OAuth scope filtering, **when** pages are
   traversed, **then** their union equals exactly the previously authorized
   catalog.
2. **Given** MCP `2026-07-28` or a supported 2025 revision, **when**
   `tools/list` is paginated, **then** the same endpoint accepts the standard
   cursor field.
3. **Given** compression disabled by configuration, **when** a large response
   is requested, **then** no application compression is applied.

## Edge Cases

- The tool count is zero, exactly one page, or one item over a page boundary.
- A cursor is empty, oversized, invalid base64, invalid JSON, wrong version,
  missing fields, or references a catalog that changed.
- OAuth scopes or startup visibility change between page requests.
- A hostile server repeats cursors, emits excessive pages, or duplicates tools
  while qmtctl is listing them.
- `Accept-Encoding` contains multiple codings or quality values.
- An upstream app already set `Content-Encoding`.
- A response uses `text/event-stream`.

## Requirements

### Functional Requirements

- **FR-001**: `tools/list` MUST use server-selected page sizes and standard
  optional `nextCursor`; clients MUST NOT be able to select arbitrary page
  sizes.
- **FR-002**: The page size MUST be configurable with
  `QMT_MCP_LIST_PAGE_SIZE`, default to 50, and reject values outside 1 through
  1000 at startup.
- **FR-003**: Tool pages MUST be sorted by tool name, contain no overlap, and
  omit `nextCursor` when exhausted.
- **FR-004**: Cursors MUST be opaque, versioned, bounded in size, and bound to a
  fingerprint of the complete request-visible tool-name set.
- **FR-005**: Invalid, stale, or cross-visibility cursors MUST return
  `-32602` without exposing their decoded representation or hidden tool names.
- **FR-006**: Startup profiles, allow/deny lists, and OAuth scopes MUST be
  applied before pagination.
- **FR-007**: Pagination MUST work for preferred MCP `2026-07-28` and supported
  2025 revisions on the existing endpoint.
- **FR-008**: qmtctl MUST follow every non-empty cursor emitted by this server,
  combine all pages, and preserve existing human and JSON output.
- **FR-009**: qmtctl MUST reject cursor cycles, excessive page counts, and
  duplicate tool names as protocol errors.
- **FR-010**: HTTP gzip MUST be negotiated only when the request accepts gzip,
  the response is not already encoded, and its body meets
  `QMT_MCP_GZIP_MIN_SIZE`.
- **FR-011**: `QMT_MCP_GZIP_MIN_SIZE` MUST default to 1024 bytes, accept zero
  as disabled, and reject values above 10 MiB or below zero.
- **FR-012**: `text/event-stream` responses MUST NOT be compressed.
- **FR-013**: Compressed responses MUST include correct `Content-Encoding`,
  `Content-Length` when known, and `Vary: Accept-Encoding`.
- **FR-014**: qmtctl MUST transparently consume gzip through the standard Go
  HTTP transport without a separate command flag.
- **FR-015**: This feature MUST NOT change tool definitions, tool-call result
  envelopes, auth challenges, audit records, or business-level result limits.
- **FR-016**: Unit and integration tests MUST run without a broker pack; remote
  CI MUST retain official conformance and native linux/amd64 image gates.
- **FR-017**: Operator and client documentation MUST describe the defaults,
  tuning knobs, proxy interaction, and the distinction between MCP catalog
  pagination and tool-specific data limits.

## Key Entities

- **Visible Tool View**: The deterministic, authorized set of tool definitions
  for one request principal and startup configuration.
- **Pagination Cursor**: A bounded versioned token containing the last emitted
  tool key and visible-view fingerprint.
- **Tool Page**: A stable slice of the visible tool view plus an optional
  continuation cursor.
- **Compression Policy**: Minimum body size and content-type/negotiation rules
  for applying HTTP gzip.

## Success Criteria

- **SC-001**: A page size of one traverses the full core catalog through modern
  and legacy paths without omission or duplication.
- **SC-002**: All malformed, stale, and cross-view cursor tests return
  `-32602`.
- **SC-003**: qmtctl combines at least three fixture pages and rejects cursor
  cycles within a bounded number of requests.
- **SC-004**: A gzip-eligible full tool page is at least 40 percent smaller than
  its uncompressed representation and decodes byte-equivalently at the JSON
  level.
- **SC-005**: Existing Python, Go, OAuth, protocol conformance, six-target CLI,
  release-policy, and native image checks remain green.

## Assumptions

- Tool names are unique and are the stable catalog key.
- The official Python SDK does not yet paginate `MCPServer` tool registrations
  automatically, so the application supplies the standard list handler.
- The official Go SDK owns MCP lifecycle and wire decoding; qmtctl adds bounded
  aggregation around its list call.
- Reverse proxies may also compress responses. Standards-compliant
  `Content-Encoding` checks prevent double compression.

## Out of Scope And Follow-on Delivery

- Pagination inside market-data tool results.
- Brotli, zstd, request-body compression, or compressed SSE.
- Durable Tasks, task input, and uncompressed task status SSE were delivered
  by 023-025.
- Resources, prompts, Apps, and Registry publication remain future work.
