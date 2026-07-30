# Verification: Task Elicitation

**Date**: 2026-07-31

**Branch**: `codex/024-task-elicitation`

## Local gates

| Gate | Result |
|---|---|
| Ruff lint and format | PASS: 92 files |
| Python unit tier | PASS: 219 passed, 1 PostgreSQL-only skipped |
| Python SDK integration tier | PASS: 38 passed |
| Go test, vet, and build | PASS |
| qmtctl cross-build | PASS: Linux/macOS/Windows, amd64/arm64 |
| Release-policy unit tests | PASS: 7 tests |
| Conventional range/title policy | PASS |
| actionlint 1.7.12 | PASS |
| Compose config | PASS: direct and TLS compositions |
| Shell syntax and diff whitespace | PASS |
| Updated skill validation | PASS: qmt-mcp-ops and deploying skill |
| linux/amd64 appliance build smoke | PASS |

The PostgreSQL test remains intentionally skipped because `QMT_TEST_DB_URL`
was not configured. Task interaction uses the existing dependency-light
SQLite store.

The linux/amd64 image was built from an arm64 Docker host using the registry
BuildKit cache. Every stable Wine/Python dependency layer was cached; the
changed application source and in-Wine smoke ran successfully. The PR gate
will repeat this on GitHub's native linux/amd64 runner.

## Official conformance

Package: `@modelcontextprotocol/conformance@0.2.0-alpha.10`

Evidence directories:

- `/tmp/qmt024-all-tasks.p8BeGc`
- `/tmp/qmt024-protocol.mSmYwc`

| Surface | Scenarios | Passed |
|---|---|---:|
| Stable server foundation | tools-list, caching, HTTP header validation | 21 |
| Stable Tasks | 023 lifecycle/capability/wire/header/dispatch scenarios plus 024 MRTR input and composition | 35 |
| Legacy server | initialize, ping, tools-list | 5 |
| Stable qmtctl client | tools_call, request metadata, standard headers | 9 |
| Legacy qmtctl client | initialize, tools_call | 2 |
| **Total** | | **72** |

All selected checks passed with no failures or warnings. The caching harness
skipped unavailable resource-read coverage, and qmtctl skipped capabilities or
methods it does not claim; these are the official scenario's normal optional
skips.

The new stable checks passed:

- `tasks/get` surfaces a non-empty standard request map at `input_required`.
- matching `tasks/update` responses resume execution.
- partial fulfillment leaves only the unanswered key.
- synchronous MRTR input resolves before durable task creation.

## Behavioral evidence

- Task input accepts standard MCP request envelopes, validates 16-item/64 KiB
  bounds, and enforces lifetime-unique keys across rounds.
- Partial, duplicate, unknown, concurrent, late, declined, and cancelled
  answers are covered; only the final pending key wakes execution.
- Pending prompts persist as a point-in-time snapshot. A sentinel answer was
  verified absent from SQLite after delivery.
- Cancellation and restart behavior remain terminal-safe; terminal tasks
  acknowledge and ignore late answers.
- OAuth refresh preserves access. A different subject or token missing the
  original scope receives indistinguishable `-32602` for both `tasks/get` and
  `tasks/update`.
- qmtctl emits structured `task_input_required` data in human and JSON output,
  validates response bounds locally, and never auto-confirms.
- Initial MRTR creates no task row. The retry creates one task, removes stale
  input fields, and its terminal result uses the supplied answer.
- Stable `2026-07-28` remains primary; supported 2025 and modern
  non-declaring clients remain synchronous.

## Remote gates

PR CI run
[`30581290887`](https://github.com/juju-w/qmt-mcp/actions/runs/30581290887)
passed all six required jobs:

- Conventional commit policy: PASS
- Python lint and unit tests: PASS
- qmtctl test and build: PASS
- MCP 2026 and legacy conformance: PASS
- Secret scan with gitleaks: PASS
- Native linux/amd64 appliance build: PASS in 2m50s

Main CI and automated release evidence remain pending delivery.
