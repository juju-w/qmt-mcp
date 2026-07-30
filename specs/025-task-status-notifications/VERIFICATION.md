# Verification: Task Status Notifications

**Date**: 2026-07-31

**Branch**: `codex/025-task-status-notifications`

## Local gates

| Gate | Result |
|---|---|
| Ruff lint and format | PASS: 94 files |
| Python unit tier | PASS: 219 passed, 1 PostgreSQL-only skipped |
| Python SDK integration tier | PASS: 48 passed |
| Task notification integration module | PASS: 8 passed |
| Go test, vet, and build | PASS |
| qmtctl cross-build | PASS: Linux/macOS/Windows, amd64/arm64 |
| Release-policy unit tests | PASS: 7 tests |
| actionlint 1.7.12 | PASS |
| Compose config | PASS: direct and TLS compositions |
| Shell syntax and diff whitespace | PASS |
| Updated skill validation | PASS: qmt-mcp-ops and deploying skill |
| Changed-file secret review | PASS |
| linux/amd64 appliance build smoke | PASS |

The PostgreSQL test remains intentionally skipped because `QMT_TEST_DB_URL`
was not configured. Feature 025 adds no database schema and uses the existing
SQLite task store plus bounded in-memory listener queues.

The linux/amd64 image was built from an arm64 Docker host with the public GHCR
BuildKit cache. Stable Wine/Python dependency layers were cached; the changed
application source, Windows Python import, and MCP startup smoke all passed.
The PR gate repeats this on GitHub's native linux/amd64 runner.

## Official conformance

Package: `@modelcontextprotocol/conformance@0.2.0-alpha.10`

Evidence directories:

- `/tmp/qmt025-conformance.ToIHRx`
- `/tmp/qmt025-notifications.SZR5iV`

| Surface | Scenarios | Passed |
|---|---|---:|
| Stable server foundation | tools-list, caching, HTTP header validation | 21 |
| Stable Tasks | lifecycle, capability, wire, header, dispatch, error, MRTR input, and composition | 35 |
| Legacy server | initialize, ping, tools-list | 5 |
| Stable qmtctl client | tools_call, request metadata, standard headers | 9 |
| Legacy qmtctl client | initialize, tools_call | 2 |
| **Executable total** | | **72** |

The selected executable checks reported zero failures and zero warnings.
Optional unsupported surfaces account for 12 expected skips and one
informational result.

The separately recorded `tasks-status-notifications` scenario reported zero
failures, but was skipped with the upstream message that status-notification
conformance is pending its `subscriptions/listen` rewrite. It is traceability,
not acceptance evidence; the project integration and Go suites are the
executable gate.

## Behavioral evidence

- Stable `2026-07-28` listeners receive an acknowledgement first, then complete
  current and changed `notifications/tasks` snapshots.
- Notifications omit response-only `resultType`, owner digests, required
  scopes, arguments, raw input responses, and credentials.
- Creation, input-required, partial input, resume, completion, protocol
  failure, tool-error completion, and cancellation publish only after durable
  state changes. Unknown, duplicate, and terminal no-op updates do not publish.
- Listener registration precedes snapshot capture, preserving transitions that
  race acknowledgement. Multiple and mixed core/task listeners remain ordered.
- Unknown, expired, cross-principal, and insufficient-scope IDs are omitted
  indistinguishably from acknowledgement and delivery.
- Listener count, task-ID count, event queue, SSE frame size, and CLI task
  deadline are bounded. A slow consumer closes without blocking publishers.
- A real uvicorn Streamable HTTP test completes `slow_compute` from SSE without
  a `tasks/get` request.
- qmtctl validates acknowledgement, subscription ID, task identity, complete
  state shape, timestamps, and ordering. Unsupported, unacknowledged,
  malformed, closed, or lost streams fall back to server-guided polling.
- qmtctl refreshes OAuth before the listen request and preserves static-token,
  detach, sync, cancellation, and supported 2025 behavior.
- The server never emits the removed `notifications/tasks/status` method.

## Remote gates

PR CI, main CI, and automated release evidence remain pending delivery.
