# Feature Specification: Tool Contracts and Profiles

**Feature Branch**: `codex/020-tool-contracts`

**Created**: 2026-07-31

**Status**: Approved

**Depends on**: 002 (MCP core), 019 (MCP 2026 protocol foundation).

## Summary

Make every exposed QMT MCP tool self-describing and machine-checkable without
changing its business payload. Each tool advertises a title, input schema,
common output-envelope schema, and accurate behavior annotations. Tool calls
return the exact JSON payload in `structuredContent`, retain a JSON text block
for legacy clients, and mark execution errors with `isError`.

Add deterministic, startup-configured tool profiles so operators can reduce
model context and exposed capability surface. Request-specific OAuth scope
filtering is deferred to 021 but must be able to reuse the same policy.

## User Scenarios & Testing

### User Story 1 - Agents receive complete tool contracts (Priority: P1)

An MCP client lists tools and can reason about their inputs, outputs, and side
effects before calling them.

**Independent Test**: Start the broker-neutral server, call `tools/list`, and
validate every returned tool against the metadata contract.

**Acceptance Scenarios**:

1. **Given** any visible tool, **when** a client lists tools, **then** the tool
   has a non-empty title and description, an object input schema, an output
   schema requiring `ok`, and all four MCP behavior annotations.
2. **Given** a read-only query tool, **when** listed, **then**
   `readOnlyHint=true`, `destructiveHint=false`, and the open-world hint
   accurately distinguishes core-local tools from QMT-backed tools.
3. **Given** a cache, subscription, sector, or generated-file mutation tool,
   **when** listed, **then** it is not mislabeled read-only and its destructive
   and idempotent hints match the operation.

---

### User Story 2 - Structured results remain backward compatible (Priority: P1)

A modern client consumes `structuredContent`; an older client can still parse
the JSON text content used before this feature.

**Independent Test**: Call successful and refused tools through MCP and compare
their structured and text payloads.

**Acceptance Scenarios**:

1. **Given** a successful call, **when** the server responds, **then**
   `structuredContent` equals the original tool dictionary, the text block
   serializes the same dictionary, and `isError=false`.
2. **Given** a validation, readiness, authorization, dependency, or internal
   tool error envelope, **when** the server responds, **then** the payload is
   preserved and `isError=true`.
3. **Given** any result, **when** the SDK validates it, **then** it conforms to
   the advertised common envelope schema without injecting or deleting
   business fields.

---

### User Story 3 - Operators choose a bounded tool profile (Priority: P1)

An operator can expose only the capability families needed by a particular
agent while keeping health and capability diagnostics available.

**Independent Test**: Build apps under each profile and inspect `tools/list`,
registry metadata, and capability output.

**Acceptance Scenarios**:

1. **Given** `full`, **when** optional gates permit a tool, **then** it remains
   visible exactly as before 020.
2. **Given** `core`, `market`, `account`, or `readonly`, **when** the app starts,
   **then** only matching tools plus the two core tools are callable and listed.
3. **Given** `custom`, **when** allowlist globs are configured, **then** only
   matching tools plus core are visible.
4. **Given** a denylist, **when** it matches a non-core tool, **then** the tool
   is neither listed nor callable. Core tools cannot be denied.
5. **Given** an invalid profile or empty custom allowlist, **when** config loads,
   **then** startup fails closed with a configuration error.

## Edge Cases

- Optional xtdata, xttrade, portfolio, sector, and formula gates run before
  profile filtering.
- A mutation-like tool name registered with read-only annotations.
- A tool error payload contains extra diagnostic fields.
- A success payload contains nested arrays, arbitrary xtdata fields, Unicode,
  dates already normalized to strings, or `null`.
- Allowlist and denylist patterns overlap; deny wins for non-core tools.
- A profile hides every optional family; core health remains available.
- A profile changes between restarts; no connection-specific state is assumed.

## Requirements

### Functional Requirements

- **FR-001**: Every listed tool MUST include a non-empty `title`,
  `description`, `inputSchema`, `outputSchema`, and `annotations`.
- **FR-002**: The common output schema MUST require boolean `ok`, describe
  standardized error fields, permit tool-specific JSON-clean fields, and use
  JSON Schema 2020-12 semantics.
- **FR-003**: Every tool call MUST return its exact dictionary payload in
  `structuredContent` and a semantically equivalent JSON `TextContent` block.
- **FR-004**: A payload with `ok=false` MUST set `isError=true`; successful
  payloads MUST set `isError=false`.
- **FR-005**: Output validation MUST NOT insert defaults, remove extra fields,
  stringify nested JSON, or otherwise change the existing business payload.
- **FR-006**: Registry registration MUST accept explicit title, read-only,
  destructive, idempotent, and open-world metadata.
- **FR-007**: The registry MUST reject known mutation-like tools that are
  accidentally registered as read-only.
- **FR-008**: Existing cache/download/subscription, custom-sector, and formula
  mutation tools MUST carry explicit non-read-only annotations.
- **FR-009**: `QMT_MCP_TOOL_PROFILE` MUST support `full`, `readonly`, `market`,
  `account`, `core`, and `custom`; default MUST be `full`.
- **FR-010**: `QMT_MCP_TOOL_ALLOWLIST` and `QMT_MCP_TOOL_DENYLIST` MUST accept
  comma-separated shell-style name globs.
- **FR-011**: Core tools MUST remain visible under every valid profile and MUST
  ignore denylist matches.
- **FR-012**: A hidden tool MUST be absent from `tools/list` and rejected as an
  unknown tool by `tools/call`.
- **FR-013**: Profile filtering MUST be deterministic and fixed for one server
  process. Readiness changes MUST NOT silently change the tool list.
- **FR-014**: `qmt_capabilities` MUST report the active profile and visible /
  hidden tool counts without exposing secrets.
- **FR-015**: Existing tool names, input arguments, success fields, error
  envelope fields, audit behavior, worker boundaries, and CLI result parsing
  MUST remain compatible.
- **FR-016**: Integration tests MUST verify metadata and result behavior through
  both the 2026 path and one legacy initialized session.
- **FR-017**: CI MUST retain official protocol conformance and appliance image
  gates introduced by 019.

## Key Entities

- **Tool Contract**: Title, descriptions, schemas, annotations, family, and
  visibility decision attached to one tool.
- **Common Result Envelope**: A JSON object requiring `ok`, with standardized
  optional error fields and unconstrained tool-specific fields.
- **Tool Profile**: A named startup policy selecting families or read-only
  contracts.
- **Visibility Policy**: Profile plus allowlist and denylist patterns; designed
  for later reuse by authorization scope filtering.

## Success Criteria

- **SC-001**: 100% of tools in every tested `tools/list` response have complete
  metadata and a common output schema.
- **SC-002**: Successful and failed tool calls preserve exact structured
  payloads and set `isError` correctly.
- **SC-003**: All six profiles produce the expected visible tool set and never
  hide core health/capability tools.
- **SC-004**: Existing Python and Go tests, selected 2026/2025 conformance, and
  the native linux/amd64 appliance build remain green.
- **SC-005**: Default `full` configuration exposes the same business tool names
  as v0.5.0 for equivalent optional feature gates.

## Out of Scope

- JWT/JWKS validation, authorization-server flows, and request-specific scope
  filtering (021).
- Pagination or transport compression (022).
- MCP Tasks (023), MCP Apps (024), Resources and Registry publication (025).
- Exact field-by-field success schemas for every xtdata raw payload; the common
  envelope is strict while broker/version-dependent success fields remain open.
- New market-data, account, analysis, or write tools.

## Assumptions

- The official Python SDK validates an annotated `CallToolResult` against its
  output model without rewriting the supplied `structuredContent`.
- Tool annotations are hints for trusted clients, not authorization controls.
- Startup profile configuration is stable for the lifetime of one process.
