# Research: Tool Contracts and Profiles

## Decision 1: Use the 2026 native tool contract

**Decision**: Emit standard MCP `title`, `inputSchema`, `outputSchema`, and
`ToolAnnotations`; do not invent a profile or visibility field on the wire.

**Evidence**:

- MCP 2026-07-28 allows full JSON Schema 2020-12 for tool inputs and outputs.
- `structuredContent` may contain any JSON value and must conform when an output
  schema is advertised.
- The standard annotations are `readOnlyHint`, `destructiveHint`,
  `idempotentHint`, and `openWorldHint`.
- `tools/list` may change by authorization, but otherwise must be deterministic
  for the requesting context.

## Decision 2: Adapt results at the registry boundary

**Decision**: Keep business functions returning their existing dictionaries.
Register a separate MCP adapter that converts the audited dictionary to a
`CallToolResult` with exact structured content, a JSON text mirror, and
`isError` derived from `ok`.

**Rationale**:

- Rewriting more than sixty business functions to return SDK objects would mix
  transport concerns into domain code and break direct unit tests.
- Returning `CallToolResult` directly lets the SDK validate the structured
  payload without serializing it through an output model that can inject
  defaults or drop broker-specific fields.
- One registry boundary guarantees identical behavior for every family.

## Decision 3: Common envelope, open success payload

**Decision**: Advertise one Pydantic common envelope requiring `ok`, defining
the standard error fields, and allowing additional fields.

**Rationale**:

- Every current tool already returns the QMT envelope.
- Many xtdata payloads vary by broker and xtquant version. Pretending their raw
  fields are closed would make the schema inaccurate.
- The contract becomes useful immediately for error handling while preserving
  version-dependent business fields. Exact schemas can be added per tool later
  without changing the envelope.

## Decision 4: Startup profiles with reusable policy

**Decision**: Implement `full`, `readonly`, `market`, `account`, `core`, and
`custom` as a pure visibility policy evaluated during registration. Apply
allowlist then denylist globs, with core always visible.

**Rationale**:

- Startup filtering reduces model context and callable surface without adding
  per-connection state to MCP 2026.
- The same policy object can accept OAuth-derived restrictions in 021.
- Filtering registration itself guarantees hidden tools are neither listed nor
  callable.

## Decision 5: Fail closed on annotation mistakes

**Decision**: Maintain a narrow set of mutation-name patterns and reject a
matching tool if it is registered with `readOnlyHint=true`.

**Rationale**: An annotation is not an authorization mechanism, but inaccurate
side-effect hints can cause clients to skip confirmation UI. Explicit mutation
metadata should be reviewed at each registration point.

## Primary Sources

- MCP 2026 tools:
  https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- MCP 2026 schema:
  https://modelcontextprotocol.io/specification/2026-07-28/schema
- Official Python SDK v2:
  https://github.com/modelcontextprotocol/python-sdk/tree/v2.0.0
