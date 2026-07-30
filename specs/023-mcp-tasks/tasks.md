# Tasks: MCP Tasks

## Phase 1 - Specification and contracts

- [x] T001 Define stable task lifecycle, compatibility, auth, and recovery.
- [x] T002 Record official SDK extension points and rejected alternatives.
- [x] T003 Add data model, wire contract, quickstart, and quality checklist.

## Phase 2 - Durable task store

- [x] T004 Add bounded task configuration and production defaults.
- [x] T005 Implement SQLite schema, secure creation, and TaskRecord mapping.
- [x] T006 Implement unguessable IDs, atomic transitions, and terminal
  immutability.
- [x] T007 Implement expiry, bounded terminal pruning, and restart recovery.
- [x] T008 Unit-test persistence, races, expiry, bounds, and sensitive-field
  exclusion.

## Phase 3 - MCP server extension

- [x] T009 Register the stable Tasks extension only for MCP `2026-07-28`.
- [x] T010 Intercept allowlisted tools and durably return task handles.
- [x] T011 Implement `tasks/get`, `tasks/update`, and `tasks/cancel`.
- [x] T012 Bind OAuth/static principals and re-check original tool scopes.
- [x] T013 Preserve synchronous legacy, modern non-declaring, and short-tool
  behavior.
- [x] T014 Add best-effort execution cancellation and startup interruption
  failure.
- [x] T015 Validate `Mcp-Method` and `Mcp-Name` routing headers after auth.
- [x] T016 Gate official conformance fixture tools behind an explicit test
  setting.

## Phase 4 - qmtctl

- [x] T017 Add Tasks capability declaration and custom method registration.
- [x] T018 Add default wait, detach, and forced sync execution modes.
- [x] T019 Add `task get`, `task wait`, `task cancel`, and `task update`.
- [x] T020 Separate per-request and overall task timeouts.
- [x] T021 Refresh OAuth on each poll and obey bounded poll guidance.
- [x] T022 Preserve existing business-command output after automatic wait.

## Phase 5 - Tests and documentation

- [x] T023 Test lifecycle, tool errors, MCP errors, cancellation, and races.
- [x] T024 Test restart recovery, expiry, retention, and SQLite failures.
- [x] T025 Test OAuth ownership/scope isolation and unauthenticated behavior.
- [x] T026 Test modern Tasks, modern synchronous, and supported 2025 sessions.
- [x] T027 Test task routing headers and stable `-32021` capability errors.
- [x] T028 Test qmtctl wait/detach/sync, resume, timeouts, and OAuth refresh.
- [x] T029 Add seven non-MRTR official stable Tasks scenarios to CI.
- [x] T030 Update README, appliance/client/CLI docs, compose, AGENT, and skills.

## Phase 6 - Verification and delivery

- [x] T031 Run ruff and Python unit/integration tests.
- [x] T032 Run Go test/vet/build and six-target cross-compilation.
- [x] T033 Run selected modern, legacy, and Tasks official conformance.
- [x] T034 Run release policy, actionlint, diff/secret review, and native image.
- [x] T035 Record evidence in `VERIFICATION.md` and close tasks accurately.
