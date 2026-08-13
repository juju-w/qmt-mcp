# Tasks: MCP 2026-07-28 Only

**Input**: `specs/029-modern-only-mcp/spec.md` and `plan.md`

## Phase 1: Protocol Contract

- [x] T001 Add the modern-only wire contract and migration examples in
  `specs/029-modern-only-mcp/contracts/protocol.md`.
- [x] T002 Add local verification commands in
  `specs/029-modern-only-mcp/quickstart.md`.

## Phase 2: Server Modern-Only Path

- [x] T003 [US1] Add bounded `/mcp` protocol-version enforcement in
  `appliance/mcp/qmt_mcp_core/app.py`.
- [x] T004 [US1] Switch the SDK Streamable HTTP app to stateless mode in
  `appliance/mcp/qmt_mcp_core/app.py`.
- [x] T005 [US2] Remove legacy SSE transport configuration in
  `appliance/mcp/qmt_mcp_core/config.py` and assembly.
- [x] T006 [US1] Update integration tests for modern discovery/list/call,
  statelessness, and modern task behavior.
- [x] T007 [US2] Add legacy initialize, missing-version, wrong-version,
  malformed-body, and no-session rejection tests.

## Phase 3: qmtctl Modern-Only Path

- [x] T008 [US3] Add a modern-only MCP round tripper in
  `cli/qmtctl/internal/qmtctl/client.go`.
- [x] T009 [US3] Verify the negotiated protocol revision before storing the
  qmtctl session.
- [x] T010 [US3] Replace fallback-success fixtures with legacy-refusal tests and
  assert no business tool call occurs.
- [x] T011 [US3] Keep Tasks and notification tests green under the strict
  transport policy.

## Phase 4: Conformance and Documentation

- [x] T012 [US4] Remove legacy MCP conformance scenarios from CI and retain
  official `2026-07-28` server/client checks.
- [x] T013 [US4] Update Chinese and English README protocol requirements and
  1.0 migration note.
- [x] T014 [US4] Update `docs/MCP-CLIENTS.md`, appliance deployment docs, and
  bundled operational skills.
- [x] T015 [US4] Update `AGENT.md` feature status after verification.

## Phase 5: Verification and Release

- [ ] T016 Run ruff, pytest unit/integration, Go test/vet/build, packaging
  script tests, actionlint, and `git diff --check`.
- [x] T017 Run official modern-only conformance and record results in
  `specs/029-modern-only-mcp/VERIFICATION.md`.
- [ ] T018 Commit with a breaking Conventional Commits marker, open a PR, and
  wait for all PR checks.
- [ ] T019 Merge after green CI, observe main CI and automatic `1.0.0` release
  to terminal success.

## Dependencies

- T001-T002 precede implementation.
- T003-T007 complete before T008-T011 so qmtctl tests have a canonical server
  contract.
- T012-T015 follow the verified implementation behavior.
- T016-T019 are the final release gate.
