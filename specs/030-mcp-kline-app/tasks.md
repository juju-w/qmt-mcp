# Tasks: Interactive K-Line MCP App

**Input**: `specs/030-mcp-kline-app/spec.md` and `plan.md`

## Phase 1: Contract and visual target

- [x] T001 Select and record visual option 2 as the implementation target.
- [x] T002 Document research, tool/resource contract, and local quickstart.

## Phase 2: App frontend

- [x] T003 Create the locked TypeScript/Vite single-file frontend workspace.
- [x] T004 Implement Apps SDK lifecycle, fixture mode, result validation, and
  host theme/locale handling.
- [x] T005 Recreate the selected responsive K-line/volume interface with
  crosshair values, moving averages, and loading/empty/error states.
- [x] T006 Implement period and dividend-adjustment refresh through the host.
- [x] T007 Add frontend tests and generate the tracked HTML resource.

## Phase 3: Server integration

- [x] T008 Extract a shared validated bars reader without changing
  `qmt_xtdata_bars` behavior.
- [x] T009 Extend the registry adapter for Apps registration and concise text
  fallback while preserving audit, annotations, profile, and OAuth behavior.
- [x] T010 Add the chart data normalizer/summary and carefully written AI-facing
  tool docstring.
- [x] T011 Register the official Python `Apps` extension and versioned HTML
  resource during server construction.

## Phase 4: Tests and documentation

- [x] T012 Add Python unit tests for normalized data, summary text, errors, and
  raw-bars parity.
- [x] T013 Add protocol integration tests for discovery, metadata,
  `resources/read`, Apps/non-Apps calls, profile, and OAuth filtering.
- [x] T014 Add CI frontend build/test/drift checks and Windows resource package
  assertions.
- [x] T015 Update Chinese/English README, client docs, and `AGENT.md` status.

## Phase 5: Verification and delivery

- [x] T016 Run Playwright visual/interaction QA at desktop/tablet/mobile and
  record `design-qa.md` with `final result: passed`.
- [ ] T017 Run ruff, all pytest tiers, npm tests/build, Go test/vet/build,
  launcher tests, packaging policy, actionlint, and `git diff --check`.
- [ ] T018 Record verification evidence, commit, open a PR, and wait for all PR
  checks.
- [ ] T019 Merge after green CI and observe main CI and release automation to a
  terminal result.

## Dependencies

- T001-T002 precede implementation.
- T003-T007 provide the immutable resource consumed by T011.
- T008-T011 complete before protocol tests.
- T012-T015 complete before visual/full verification.
- T016-T019 are the final delivery gate.
