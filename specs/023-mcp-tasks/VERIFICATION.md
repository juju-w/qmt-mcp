# Verification: MCP Tasks

**Date**: 2026-07-31

**Branch**: `codex/023-mcp-tasks`

## Local gates

| Gate | Result |
|---|---|
| Ruff lint and format | PASS: 92 files |
| Python unit tier | PASS: 219 passed, 1 PostgreSQL-only skipped |
| Python SDK integration tier | PASS: 32 passed |
| Go test, vet, and build | PASS |
| qmtctl cross-build | PASS: Linux/macOS/Windows, amd64/arm64 |
| Release-policy unit tests | PASS: 7 tests |
| actionlint 1.7.12 | PASS |
| Compose config | PASS: direct and TLS compositions |
| Diff whitespace and focused secret review | PASS |

The PostgreSQL test remains intentionally skipped because
`QMT_TEST_DB_URL` was not configured. Tasks use dependency-light SQLite and
their persistence tests ran in the unit tier.

## Official conformance

Package: `@modelcontextprotocol/conformance@0.2.0-alpha.10`

Evidence directory:
`/tmp/qmt-023-conformance-final-2`

| Surface | Scenarios | Passed |
|---|---|---:|
| Stable server foundation | tools-list, caching, HTTP header validation | 21 |
| Stable Tasks | lifecycle, capability negotiation, wire fields, request-state removal, request headers, dispatch/envelope, required-task error | 31 |
| Legacy server | initialize, ping, tools-list | 5 |
| Stable qmtctl client | tools_call, request metadata, standard headers | 9 |
| Legacy qmtctl client | initialize, tools_call | 2 |
| **Total** | | **68** |

All selected checks passed with no failures or warnings. Optional checks for
unimplemented resource methods and unrelated client capabilities were skipped
by the official harness.

The first full run found that conformance-only fixture tools lacked
descriptions when combined with `tools-list`. Descriptions were added under the
existing explicit fixture gate, and the entire matrix then passed from the
start.

## Behavioral evidence

- Task creation is durable before its handle is returned.
- Completion, application-level tool errors, MCP errors, cancellation, races,
  restart recovery, expiry, and bounded terminal retention are covered.
- OAuth refresh preserves owner access; a different principal or reduced
  original scope receives indistinguishable `-32602`.
- qmtctl waits by default, detaches without polling, forces synchronous
  compatibility mode, sends stable routing headers, and observes initial and
  subsequent server polling guidance.
- Stable `2026-07-28` advertises Tasks; supported 2025 and modern
  non-declaring clients remain synchronous.

## PR gates

GitHub Actions run
[`30578733379`](https://github.com/juju-w/qmt-mcp/actions/runs/30578733379)
passed all six jobs on PR #15:

- Conventional commit policy
- Python lint and unit tests
- Stable/legacy MCP conformance
- Full-history gitleaks
- qmtctl test and build
- Native linux/amd64 BuildKit appliance image

The image gate completed in 1 minute 56 seconds using the configured persistent
cache path.
