# Verification: MCP Pagination and HTTP Compression

**Date**: 2026-07-31

## Runtime and application tests

- `ruff check .`: passed.
- `ruff format --check .`: passed (88 files).
- Dependency-light Python 3.12 tier with only pytest and ruff installed:
  206 passed, 3 optional tiers skipped.
- Full Python 3.12 unit tier: 206 passed, 1 PostgreSQL test skipped, 28
  integration tests deselected.
- Official-SDK integration tier: 28 passed.
- `go test -race ./...`, `go vet ./...`, `go build ./...`, and the conformance
  adapter build: passed.
- qmtctl cross-compilation passed for Linux, macOS, and Windows on amd64 and
  arm64.

## Feature evidence

- Modern and legacy `tools/list` traverse one-item pages without omissions or
  overlap and reject invalid cursors with `-32602`.
- Cursor unit tests cover deterministic ordering, exact/empty boundaries,
  malformed and oversized input, duplicate keys, and visible-view changes.
- gzip tests cover identity, explicit gzip, quality values including `q=0`,
  wildcard negotiation, JSON equivalence, at least 40 percent size reduction,
  and successful uncompressed SSE streaming.
- qmtctl tests cover modern three-page gzip aggregation, retained result
  metadata, cursor-cycle refusal, and duplicate-tool refusal.
- A real Python server with page size 1 and gzip threshold 1 was consumed by
  the real qmtctl client. It issued modern discovery plus two list requests and
  returned both tools with `_meta`, `resultType`, `ttlMs`, and `cacheScope`.

## Official MCP conformance

Runner: `@modelcontextprotocol/conformance@0.2.0-alpha.10`.

| Target | Revision | Result |
|---|---|---|
| Server tools-list/caching/header validation | 2026-07-28 | 21 passed |
| Server initialize/ping/tools-list | 2025-11-25 | 5 passed |
| qmtctl tools-call/request-metadata/standard headers | 2026-07-28 | 9 passed |
| qmtctl initialize/tools-call | 2025-11-25 | 2 passed |

No expected-failure file is used.

## Repository checks

- Release-policy unit tests: 7 passed.
- actionlint 1.7.12: passed.
- Compose rendering, shell syntax, and `git diff --check`: passed.
- Six qmtctl targets built successfully.
- Changed paths contain no `.env`, broker pack, account data, personal
  strategy, screenshots, or local scripts.

## Pending remote gate

The PR must pass gitleaks and the native linux/amd64 appliance build/smoke
before T023 and T024 are closed.
