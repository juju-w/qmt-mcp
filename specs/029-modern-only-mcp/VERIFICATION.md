# Verification: MCP 2026-07-28 Only

**Date**: 2026-08-14

## Automated tests

- Python lint and format: Ruff 0.13.2 passed for 99 files.
- Python unit tier: 240 passed, 1 PostgreSQL test skipped because
  `QMT_TEST_DB_URL` was not configured.
- Python integration tier: 54 passed, including modern protocol rejection,
  OAuth, Tasks, MRTR, task notifications, pagination, and gzip.
- Go: `go test ./...`, `go vet ./...`, `go build ./...`, and the conformance
  adapter build passed with Go 1.25.
- Release policy: 16 tests passed.
- Workflow validation: actionlint 1.7.12 passed.
- Deployment verifier: 6 tests passed; the shell probe now uses stateless
  `server/discover` and per-request modern headers/metadata.

The local Mac did not have `dotnet`, so launcher restore/build/test was left to
the unchanged macOS and Windows CI jobs.

## Official MCP conformance

Pinned package: `@modelcontextprotocol/conformance@0.2.0-alpha.10`

Server scenarios passed on MCP `2026-07-28`:

- `tools-list`, `caching`, `http-header-validation`
- `tasks-lifecycle`, `tasks-capability-negotiation`, `tasks-wire-fields`
- `tasks-request-state-removal`, `tasks-request-headers`
- `tasks-dispatch-and-envelope`, `tasks-required-task-error`
- `tasks-mrtr-input`, `tasks-mrtr-composition`

Client scenarios passed on MCP `2026-07-28`:

- `tools_call`
- `request-metadata`
- `http-standard-headers`

The pinned conformance package reports `tasks-status-notifications` as skipped
pending its `subscriptions/listen` rewrite. The repository integration suite is
the executable gate for acknowledgement, current/terminal ordering, reconnect,
backpressure, and OAuth isolation.

## Breaking behavior checks

- Missing, 2025, future, malformed, and oversized protocol requests return
  HTTP 400 with JSON-RPC `-32022` and no `Mcp-Session-Id`.
- Standalone GET/DELETE on `/mcp` return HTTP 405 and do not establish a
  session.
- `QMT_MCP_TRANSPORT=sse` is rejected; `http` remains an alias for stateless
  Streamable HTTP.
- qmtctl stops the official SDK's initialize fallback before the request reaches
  a legacy-only fixture and performs no business tool call.
- Modern discovery, tool calls, OAuth, Tasks, and task notifications remain
  functional without protocol session affinity.

## Release gate

The feature commit and PR title use a breaking Conventional Commits marker.
Release automation, rather than a source edit to `VERSION`, must resolve the
next version from `0.14.5` to `1.0.0` after main CI succeeds.
