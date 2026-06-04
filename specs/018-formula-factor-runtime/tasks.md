# Tasks: Formula & Factor Runtime

## Phase A — Config & Policy

- [ ] T001 Add config for `QMT_ENABLE_FORMULA_RUNTIME`, formula allowlist, output
  sandbox path, default timeouts, and max output limits.
- [ ] T002 Implement formula allowlist schema with aliases, real formula names,
  allowed periods, max codes, max ranges, output bounds, and param schemas.
- [ ] T003 Implement parameter validation for allowed keys, types, defaults, and
  numeric/string bounds.
- [ ] T004 Add capability checks for formula call, batch, generation,
  subscription, and unsubscribe functions.

## Phase B — Serializers & Cache

- [ ] T005 Serialize `call_formula` output into JSON-clean timelist/output arrays.
- [ ] T006 Serialize `call_formula_batch` output with per-code/formula
  diagnostics.
- [ ] T007 Implement sandbox path validation and generated-factor metadata.
- [ ] T008 Implement latest-only formula callback cache with freshness metadata.

## Phase C — MCP Tools

- [ ] T009 Register `qmt_xtdata_formula_call` behind the runtime flag.
- [ ] T010 Register `qmt_xtdata_formula_call_batch`.
- [ ] T011 Register `qmt_xtdata_formula_generate_factor`.
- [ ] T012 Register `qmt_xtdata_formula_subscribe`.
- [ ] T013 Register `qmt_xtdata_formula_unsubscribe`.
- [ ] T014 Register `qmt_xtdata_formula_subscriptions`.
- [ ] T015 Register `qmt_xtdata_formula_cache`.
- [ ] T016 Update health/capabilities with runtime state, safe aliases, and
  sandbox metadata.
- [ ] T017 Audit formula calls with formula alias, code count, date range,
  parameter keys, output size, and status.

## Phase D — CLI & Docs

- [ ] T018 Add `qmtctl formula call`.
- [ ] T019 Add `qmtctl formula batch`.
- [ ] T020 Add `qmtctl formula generate`.
- [ ] T021 Add `qmtctl formula subscribe`.
- [ ] T022 Add `qmtctl formula unsubscribe`.
- [ ] T023 Add `qmtctl formula subscriptions`.
- [ ] T024 Add `qmtctl formula cache`.
- [ ] T025 Update README/qmtctl docs with formula allowlist and sandbox examples.

## Phase E — Tests & Verification

- [ ] T026 Unit-test disabled runtime refuses before xtdata calls.
- [ ] T027 Unit-test allowlist and parameter schema validation.
- [ ] T028 Unit-test call/batch serializers and output bounds.
- [ ] T029 Unit-test sandbox path validation for generated factor files.
- [ ] T030 Unit-test formula subscription callback cache and unsubscribe cleanup.
- [ ] T031 Unit-test qmtctl command-to-tool mappings.
- [ ] T032 Run host CI tier: ruff, format, pytest, Go test/vet/build.
- [ ] T033 Manual smoke only when a compatible 投研端 formula environment and
  allowlisted test formula are available.
