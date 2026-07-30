# Tasks: Task Elicitation

## Phase 1 - Specification and contracts

- [x] T001 Define stable task input, partial fulfillment, MRTR composition, and
  dual-line compatibility.
- [x] T002 Record official SDK/conformance behavior, bounds, persistence, and
  rejected alternatives.
- [x] T003 Add data model, wire contract, quickstart, and quality checklist.

## Phase 2 - Durable lifecycle operations

- [x] T004 Add bounded validation for standard input request snapshots.
- [x] T005 Add atomic partial snapshot replacement and final resume operations
  to `TaskStore`.
- [x] T006 Preserve terminal immutability and restart interruption behavior.
- [x] T007 Unit-test empty/malformed/oversized snapshots, partial updates,
  races, and no response persistence.

## Phase 3 - Task interaction runtime

- [x] T008 Add a per-task async interaction coordinator and context-local tool
  helper.
- [x] T009 Deliver exact-key responses, ignore unknown/satisfied keys, and wake
  only after complete fulfillment.
- [x] T010 Support multiple rounds with lifetime-unique request keys.
- [x] T011 Wake/cancel waiters on terminal transitions and remove coordinators
  after execution.
- [x] T012 Re-check principal ownership and original scopes on every update.

## Phase 4 - MRTR composition and fixtures

- [x] T013 Replace the `confirm_delete` shortcut with the reusable interaction
  helper and a standard `elicitation/create` envelope.
- [x] T014 Add the two-request `multi_input` gated fixture.
- [x] T015 Route initial MRTR-before-task calls synchronously and taskify only
  retries carrying input responses.
- [x] T016 Add the context-aware `test_tool_with_task` gated fixture.
- [x] T017 Confirm all fixtures remain absent unless the explicit conformance
  setting is enabled.

## Phase 5 - qmtctl

- [x] T018 Validate `--responses-json` as a bounded object before transport.
- [x] T019 Render task ID and pending requests clearly when wait stops at
  `input_required`.
- [x] T020 Test malformed, oversized, partial, human, and JSON response flows.

## Phase 6 - Tests and documentation

- [x] T021 Test single-round acceptance, decline/cancel, and completion.
- [x] T022 Test partial fulfillment, duplicate retries, unknown keys, and
  concurrent final responses.
- [x] T023 Test multiple rounds, cancellation races, terminal late updates,
  and restart recovery.
- [x] T024 Test OAuth ownership/scope isolation and sensitive-response
  exclusion from SQLite/log/audit state.
- [x] T025 Test MRTR-to-task ordering and no orphan task creation.
- [x] T026 Regress modern Tasks, modern non-declaring, and supported 2025
  clients.
- [x] T027 Add `tasks-mrtr-input` and `tasks-mrtr-composition` to pinned CI
  conformance.
- [x] T028 Update README, MCP client, CLI, test, operator, AGENT, and skill
  documentation.

## Phase 7 - Verification and delivery

- [x] T029 Run ruff and Python unit/integration tests.
- [x] T030 Run Go test/vet/build and six-target cross-compilation.
- [x] T031 Run selected modern, legacy, 023 Tasks, and 024 MRTR conformance.
- [x] T032 Run release policy, actionlint, diff/secret review, and native image
  smoke.
- [x] T033 Record evidence in `VERIFICATION.md`, close tasks accurately, and
  deliver through PR, main CI, and release.
