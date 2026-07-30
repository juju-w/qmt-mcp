# Tasks: MCP Pagination and HTTP Compression

## Phase 1 - Specification and contracts

- [x] T001 Define catalog pagination, cursor invalidation, and gzip behavior.
- [x] T002 Record official SDK extension points and rejected alternatives.
- [x] T003 Add requirement quality checklist.

## Phase 2 - Server pagination

- [x] T004 Add bounded page-size and gzip configuration.
- [x] T005 Implement dependency-light cursor encode/decode and view binding.
- [x] T006 Add deterministic tool pagination after visibility filtering.
- [x] T007 Map malformed and stale cursors to JSON-RPC `-32602`.
- [x] T008 Preserve modern cache hints and legacy session behavior.

## Phase 3 - HTTP compression

- [x] T009 Add negotiated gzip for eligible MCP responses.
- [x] T010 Exclude SSE, already encoded, small, and non-negotiated responses.
- [x] T011 Expose defaults and disable/tuning settings through compose.

## Phase 4 - qmtctl

- [x] T012 Aggregate all `tools/list` pages through the official Go SDK.
- [x] T013 Add cursor-cycle, page-count, and duplicate-name guards.
- [x] T014 Verify standard Go transport gzip decoding.

## Phase 5 - Tests and documentation

- [x] T015 Unit-test cursor boundaries, determinism, view changes, and config.
- [x] T016 Test modern and legacy multi-page traversal and invalid cursors.
- [x] T017 Test gzip negotiation, size reduction, JSON equivalence, and SSE.
- [x] T018 Test qmtctl pagination, gzip, cycles, and unchanged single-page flow.
- [x] T019 Update README, deployment/client docs, AGENT, compose, and ops skill.

## Phase 6 - Verification and delivery

- [x] T020 Run ruff and Python unit/integration tests.
- [x] T021 Run Go test/vet/build and six-target cross-compilation.
- [x] T022 Run selected modern/legacy official conformance.
- [x] T023 Run release policy, actionlint, diff/secret review, and native image.
- [x] T024 Record evidence in `VERIFICATION.md` and close tasks accurately.
