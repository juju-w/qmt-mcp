# Tasks: Custom Sector Management

## Phase A — Config & Policy

- [ ] T001 Add server config for `QMT_ENABLE_XTDATA_SECTOR_WRITE` and allowed
  sector prefixes.
- [ ] T002 Implement sector policy validation for enabled flag, prefix allowlist,
  built-in sector refusal, max code count, and destructive confirmation.
- [ ] T003 Add capability checks for official sector mutation APIs.

## Phase B — MCP Tools

- [ ] T004 Register `qmt_xtdata_sector_create_folder` behind the write flag.
- [ ] T005 Register `qmt_xtdata_sector_create` behind the write flag.
- [ ] T006 Register `qmt_xtdata_sector_add_codes`.
- [ ] T007 Register `qmt_xtdata_sector_remove_codes`.
- [ ] T008 Register `qmt_xtdata_sector_delete` with `confirm=true`.
- [ ] T009 Register `qmt_xtdata_sector_reset` with `confirm=true`.
- [ ] T010 Register `qmt_xtdata_managed_sector_list`.
- [ ] T011 Update health/capabilities with sector-write state and prefix policy.
- [ ] T012 Audit every mutation with operation, sector, code count, policy, and
  result status.

## Phase C — CLI & Docs

- [ ] T013 Add `qmtctl sector create-folder`.
- [ ] T014 Add `qmtctl sector create`.
- [ ] T015 Add `qmtctl sector add`.
- [ ] T016 Add `qmtctl sector remove`.
- [ ] T017 Add `qmtctl sector delete`.
- [ ] T018 Add `qmtctl sector reset`.
- [ ] T019 Add `qmtctl sector list-managed`.
- [ ] T020 Update README/qmtctl docs with disabled-by-default behavior and prefix
  examples.

## Phase D — Tests & Verification

- [ ] T021 Unit-test disabled writes refuse before xtdata calls.
- [ ] T022 Unit-test prefix policy and built-in sector refusal.
- [ ] T023 Unit-test create/add/remove/delete/reset with fake xtdata.
- [ ] T024 Unit-test confirmation requirement for destructive operations.
- [ ] T025 Unit-test qmtctl command-to-tool mappings.
- [ ] T026 Run host CI tier: ruff, format, pytest, Go test/vet/build.
- [ ] T027 Manual smoke only on an isolated `MCP/Test` sector.
