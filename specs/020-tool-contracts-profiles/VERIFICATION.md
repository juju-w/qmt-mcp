# Verification: Tool Contracts and Profiles

**Date**: 2026-07-31

## Tool contract behavior

- Modern `2026-07-28` and legacy `2025-11-25` integration tests validate every
  listed tool's title, description, input schema, common output schema, and all
  four behavior hints.
- Successful and refused calls preserve exact business dictionaries in
  `structuredContent`; parsed JSON text is equal and `isError` follows `ok`.
- The default `full` profile exposes every otherwise registered tool.
- The `core` profile lists only `qmt_health` and `qmt_capabilities`; a hidden
  xtdata tool is rejected by `tools/call`.
- Pure policy tests cover all six profiles, allow/deny precedence, immutable
  core visibility, invalid profiles, and empty custom allowlists.
- Explicit behavior tests cover quote subscription/history, reference
  downloads, managed sectors, and formula generation/subscriptions.

## Local quality gates

- `ruff check .`: passed.
- `ruff format --check .`: passed (83 files).
- Python 3.12 unit tier: 172 passed; one PostgreSQL test skipped because
  `QMT_TEST_DB_URL` was not configured.
- Python 3.12 official-SDK integration tier: 10 passed.
- Compose interpolation/schema validation: passed.
- `go test ./...`, `go vet ./...`, normal builds, and conformance-driver build:
  passed.
- qmtctl cross-compilation: Linux, macOS, and Windows on amd64 and arm64 passed.
- Release-policy unit tests: 7 passed.
- actionlint 1.7.12 and `git diff --check`: passed.

## Official MCP conformance

Runner: `@modelcontextprotocol/conformance@0.2.0-alpha.10`.

| Target | Version | Scenario | Result |
|---|---|---|---|
| Server | 2026-07-28 | `tools-list` | 2/2 passed |
| Server | 2025-11-25 | `tools-list` | 2/2 passed |
| qmtctl client | 2026-07-28 | `tools_call` | 1/1 passed |
| qmtctl client | 2025-11-25 | `tools_call` | 1/1 passed |

## Pending delivery evidence

- Native GitHub `linux/amd64` appliance image gate.
- Remaining PR checks, merge, main CI, and automated release.
