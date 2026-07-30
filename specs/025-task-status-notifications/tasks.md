# Tasks: Task Status Notifications

## Phase 1 - Specification and contracts

- [x] T001 Define stable listen/filter/notification behavior, compatibility,
  authorization, reconnect, and fallback.
- [x] T002 Record official protocol, SDK limitations, conformance status,
  bounds, and rejected alternatives.
- [x] T003 Add data model, wire contract, quickstart, and quality checklist.

## Phase 2 - Notification protocol runtime

- [x] T004 Add typed task subscription filters, task events, and full
  `notifications/tasks` wire models.
- [x] T005 Add a bounded Tasks-aware listen handler that preserves core
  subscription filters.
- [x] T006 Validate/deduplicate task IDs and acknowledge only authorized
  owner/scope matches.
- [x] T007 Subscribe before snapshot capture, acknowledge first, emit current
  snapshots, and stamp every frame with the subscription ID.
- [x] T008 Close and clean up disconnected, graceful, and slow-consumer
  streams without blocking publishers.
- [x] T009 Install the handler on the existing MCP server and shared `/mcp`
  transport without patching the SDK.

## Phase 3 - Lifecycle publication

- [x] T010 Add complete client-visible notification serialization without
  `resultType` or storage-only fields.
- [x] T011 Publish task create, input-required, partial-input, and resume
  transitions after durable commit.
- [x] T012 Publish completed, failed, tool-error-completed, and cancelled
  transitions after durable commit.
- [x] T013 Suppress fabricated events for unknown, duplicate, terminal, or
  otherwise no-op updates.
- [x] T014 Preserve per-task order under completion/cancel/input races and
  publish immutable terminal state.

## Phase 4 - Server tests

- [x] T015 Unit-test filter bounds, deduplication, capability gating, complete
  shapes, metadata, and removed-method absence.
- [x] T016 Unit-test current-state race handling, mixed standard filters,
  multiple listeners, slow consumers, and cleanup.
- [x] T017 Integration-test acknowledgement-first, no-poll completion,
  failure, cancellation, and terminal-at-subscribe.
- [x] T018 Integration-test elicitation, partial input, resume ordering,
  reconnect, expiry, and restart state.
- [x] T019 Integration-test OAuth owner/scope isolation, mixed authorized
  IDs, static-token mode, and no sensitive-field leakage.
- [x] T020 Regress supported 2025, modern non-declaring, and modern polling
  clients.

## Phase 5 - qmtctl

- [x] T021 Add a bounded extension-aware Streamable HTTP SSE listener for one
  task ID with OAuth/static-token headers.
- [x] T022 Prefer matching notification snapshots in automatic wait and
  preserve the overall task deadline.
- [x] T023 Fall back to server-guided polling on unsupported, unacknowledged,
  malformed, closed, or lost streams.
- [x] T024 Test zero-poll notification success, every fallback, stale/foreign
  snapshots, OAuth refresh, cancellation, and timeout.

## Phase 6 - CI and documentation

- [x] T025 Add the pinned official `tasks-status-notifications` scenario to CI
  and record its pending skip separately from executable project acceptance.
- [x] T026 Update README, MCP client, CLI, operator, test, AGENT, and qmt-mcp
  skill documentation with stable-first notification/fallback guidance.
- [x] T027 Close 024 delivery evidence and remove superseded 019/020/021
  roadmap wording for 024/025.

## Phase 7 - Verification and delivery

- [x] T028 Run ruff and Python unit/integration tests.
- [x] T029 Run Go test/vet/build and six-target cross-compilation.
- [x] T030 Run selected modern, legacy, all Tasks, MRTR, and notification
  conformance.
- [x] T031 Run release policy, actionlint, compose, skill validation,
  diff/secret review, and native linux/amd64 image smoke.
- [ ] T032 Record evidence in `VERIFICATION.md`, close tasks accurately, and
  deliver through PR, main CI, and automated release.
