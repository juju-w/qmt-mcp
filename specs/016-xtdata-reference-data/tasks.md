# Tasks: xtdata Reference Data

## Phase A — Validation & Capabilities

- [ ] T001 Add validators for financial table names, report type, code count,
  date ranges, output row limits, and reference command enum values.
- [ ] T002 Add capability helpers for optional xtdata reference functions.
- [ ] T003 Define normalized response metadata for source, generated_at,
  capabilities, row_count, truncated, and diagnostics.

## Phase B — Serializers

- [ ] T004 Serialize `get_financial_data` nested dict/DataFrame output into
  grouped JSON rows.
- [ ] T005 Serialize dividend-factor DataFrame output.
- [ ] T006 Serialize IPO list/dict rows with normalized field aliases.
- [ ] T007 Serialize CB and ETF metadata outputs with bounded row counts.
- [ ] T008 Serialize download/status results for reference-data refresh calls.

## Phase C — MCP Tools

- [ ] T009 Register `qmt_xtdata_financial_data`.
- [ ] T010 Register `qmt_xtdata_download_financial_data`.
- [ ] T011 Register `qmt_xtdata_dividend_factors`.
- [ ] T012 Register `qmt_xtdata_ipo_info`.
- [ ] T013 Register `qmt_xtdata_download_cb_data`.
- [ ] T014 Register `qmt_xtdata_cb_info`.
- [ ] T015 Register `qmt_xtdata_download_etf_info`.
- [ ] T016 Register `qmt_xtdata_etf_info`.
- [ ] T017 Register `qmt_xtdata_download_holiday_data`.
- [ ] T018 Register `qmt_xtdata_download_history_contracts`.
- [ ] T019 Register `qmt_xtdata_period_list`.
- [ ] T020 Audit reference calls with bounded code/table/date/count summaries.

## Phase D — CLI & Docs

- [ ] T021 Add `qmtctl ref financial`.
- [ ] T022 Add `qmtctl ref download-financial`.
- [ ] T023 Add `qmtctl ref dividends`.
- [ ] T024 Add `qmtctl ref ipo`.
- [ ] T025 Add `qmtctl ref cb`.
- [ ] T026 Add `qmtctl ref etf`.
- [ ] T027 Add `qmtctl ref periods`.
- [ ] T028 Update README and qmtctl docs with reference-data commands and
  xttrade-vs-xtdata IPO distinction.

## Phase E — Tests & Verification

- [ ] T029 Unit-test validators and unsupported-function diagnostics.
- [ ] T030 Unit-test financial, dividend, IPO, CB, ETF, and period serializers.
- [ ] T031 Unit-test MCP tool envelopes with fake xtdata functions.
- [ ] T032 Unit-test qmtctl command-to-tool mappings.
- [ ] T033 Run host CI tier: ruff, format, pytest, Go test/vet/build.
- [ ] T034 NAS/manual smoke: financial query, IPO range query, dividend query,
  and one optional CB/ETF capability check.
