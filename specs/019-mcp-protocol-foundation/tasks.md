# Tasks: MCP Protocol Foundation

## Phase 1 - Specification and protocol tests

- [x] T001 Record stable-version, FastMCP, lock, and conformance decisions in
  `specs/019-mcp-protocol-foundation/`.
- [x] T002 Add integration tests for modern discover/stateless/header/cache
  behavior and legacy initialize/session behavior at one endpoint.
- [x] T003 Add the qmtctl conformance adapter at
  `cli/qmtctl/cmd/conformance/main.go`.

## Phase 2 - Official SDK migration

- [x] T004 Replace FastMCP with official MCP Python SDK 2.0.0 `MCPServer`.
- [x] T005 Preserve the explicit registry, audit wrappers, worker boundaries,
  health state, auth wrapper, and tool set during migration.
- [x] T006 Serve modern stateless and legacy stateful traffic on `/mcp`.
- [x] T007 Replace handwritten qmtctl MCP RPC with official Go SDK 1.7.0
  modern-first negotiation and fallback.
- [x] T008 Preserve qmtctl static bearer auth, timeouts, tool-result unwrapping,
  and error envelopes.
- [x] T009 Update qmtctl development, CI, and release builders to Go 1.25.

## Phase 3 - Reproducible runtime

- [x] T010 Pin direct dependencies in `appliance/mcp/requirements.in`.
- [x] T011 Generate and commit the complete Python 3.12 runtime lock at
  `appliance/mcp/requirements.txt`.
- [x] T012 Switch `appliance/Dockerfile` dependency installation to the lock
  while preserving the cache boundary.
- [x] T013 Validate the lock in clean Linux Python 3.12 and Windows Python 3.12
  target resolution.

## Phase 4 - CI conformance

- [x] T014 Install the runtime lock and run integration tests in a dedicated CI
  protocol job.
- [x] T015 Start a no-broker, no-xtdata loopback QMT MCP server in CI.
- [x] T016 Run selected pinned official 2026 server conformance scenarios.
- [x] T017 Run selected pinned official 2025 server conformance scenarios.
- [x] T018 Build the qmtctl conformance adapter and run selected modern and
  legacy client scenarios.
- [x] T019 Ensure conformance uses no expected-failure baseline.

## Phase 5 - Documentation and verification

- [x] T020 Update README, CLI README, AGENT, and test documentation with the
  preferred modern protocol, legacy compatibility, and conformance commands.
- [x] T021 Run ruff lint/format and Python unit/integration tests.
- [x] T022 Run Go test, vet, and builds for qmtctl and its conformance adapter.
- [x] T023 Run release-policy tests, actionlint, `git diff --check`, and secret
  review.
- [x] T024 Build/smoke the linux/amd64 appliance dependency layer.
- [x] T025 Record command evidence and any environment limitations in
  `specs/019-mcp-protocol-foundation/VERIFICATION.md`.
- [x] T026 Mark completed tasks only after their verification evidence exists.
- [x] T027 Add a cached native linux/amd64 appliance build to PR/main CI and
  reuse that cache in release.
