# Tasks: Option Chain & Volatility Inputs

## Phase A — Capability & Validation

- [ ] T001 Detect xtdata option API capabilities:
  `get_option_undl_data`, `get_option_list`, `get_option_detail_data`,
  `get_option_iv`, BSM helpers, and historical-contract support.
- [ ] T002 Add validators for underlying code, expiry date/month, option type,
  max expiries, max contracts, max quote fanout, and quote policy.
- [ ] T003 Define built-in option family aliases for 50ETF, 300ETF, 500ETF,
  科创50ETF, 创业板ETF, and index-option families when available.

## Phase B — Serializers & Models

- [ ] T004 Implement option detail normalization: code, underlying, CALL/PUT,
  expiry, strike, unit, risk-free rate, historical volatility, trading status.
- [ ] T005 Implement option chain grouping by expiry, strike, and option type.
- [ ] T006 Implement option quote normalization from existing snapshot/full-tick
  fields, including bid/ask midpoint and quote freshness metadata.
- [ ] T007 Implement volatility-index input packaging with underlying quote,
  expiry groups, paired CALL/PUT strike rows, midpoint fields, and diagnostics.

## Phase C — MCP Tools

- [ ] T008 Register `qmt_xtdata_option_underlyings`.
- [ ] T009 Register `qmt_xtdata_option_chain`.
- [ ] T010 Register `qmt_xtdata_option_detail`.
- [ ] T011 Register `qmt_xtdata_option_quotes`.
- [ ] T012 Register `qmt_xtdata_option_iv`.
- [ ] T013 Register `qmt_xtdata_volatility_index_inputs`.
- [ ] T014 Audit option tool calls with bounded code/count summaries.

## Phase D — CLI & Docs

- [ ] T015 Add `qmtctl option underlyings`.
- [ ] T016 Add `qmtctl option chain`.
- [ ] T017 Add `qmtctl option detail`.
- [ ] T018 Add `qmtctl option quotes`.
- [ ] T019 Add `qmtctl option iv`.
- [ ] T020 Add `qmtctl option vix-inputs`.
- [ ] T021 Update README and qmtctl docs with option/VIX input workflows and
  entitlement caveats.

## Phase E — Tests & Verification

- [ ] T022 Unit-test capability detection for present/missing option APIs.
- [ ] T023 Unit-test chain grouping and CALL/PUT pairing.
- [ ] T024 Unit-test option detail and quote serializers with fake xtdata data.
- [ ] T025 Unit-test volatility-index input package shape and diagnostics.
- [ ] T026 Unit-test qmtctl command-to-tool mappings.
- [ ] T027 Run host CI tier: ruff, format, pytest, Go test/vet/build.
- [ ] T028 NAS/manual smoke: resolve a real option family, fetch chain, quote
  selected CALL/PUT contracts, and produce a VIX input package.
