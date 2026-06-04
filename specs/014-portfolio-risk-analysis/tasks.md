# Tasks: Portfolio Risk Analysis

## Phase A — Pure Calculation Layer

- [ ] T001 Define normalized portfolio input records for asset, position, quote,
  and metadata.
- [ ] T002 Implement position valuation and weight calculations.
- [ ] T003 Implement unrealized P&L calculations with missing-cost diagnostics.
- [ ] T004 Implement concentration metrics: max position, top-N, and position
  count.
- [ ] T005 Implement exposure grouping by market and instrument type.
- [ ] T006 Implement best-effort sector/theme exposure using 006 metadata.
- [ ] T007 Implement threshold validation and default risk checks.

## Phase B — MCP Tool Family

- [ ] T008 Create `qmt_mcp_portfolio` package.
- [ ] T009 Register `qmt_portfolio_summary`.
- [ ] T010 Register `qmt_portfolio_positions`.
- [ ] T011 Register `qmt_portfolio_exposure`.
- [ ] T012 Register `qmt_portfolio_risk_checks`.
- [ ] T013 Enforce 004 account allowlist and readiness boundaries for every
  account-scoped tool.
- [ ] T014 Implement quote policy integration (`prefer_cache`, `live`,
  `cache_only`) with 003/013 quote sources.
- [ ] T015 Add partial-data diagnostics for missing/stale quotes and missing
  metadata.
- [ ] T016 Audit portfolio calls with account id and bounded summaries only.
- [ ] T017 Document that optional Codex skills may consume portfolio outputs but
  must not bypass MCP account access or duplicate core calculations.

## Phase C — Health & Configuration

- [ ] T018 Add portfolio feature flag/config defaulting to disabled until
  dependencies are available.
- [ ] T019 Add portfolio family capability state to health/capabilities.
- [ ] T020 Ensure disabled/not_authorized/not_ready/degraded/enabled states are
  covered by tests.

## Phase D — qmtctl CLI

- [ ] T021 Add `qmtctl portfolio summary --account <id>`.
- [ ] T022 Add `qmtctl portfolio positions --account <id>`.
- [ ] T023 Add `qmtctl portfolio exposure --account <id>`.
- [ ] T024 Add `qmtctl portfolio risk --account <id>` with threshold flags.
- [ ] T025 Add quote policy flags and JSON/human output coverage.

## Phase E — Tests

- [ ] T026 Unit-test deterministic summary metrics with fake positions/assets/
  quotes.
- [ ] T027 Unit-test missing quote and stale quote handling.
- [ ] T028 Unit-test unknown account refusal before analysis data is returned.
- [ ] T029 Unit-test threshold pass/warn/fail outputs.
- [ ] T030 Unit-test qmtctl command-to-tool mappings.
- [ ] T031 Run host CI tier: ruff, format, pytest, Go test/vet/build.

## Phase F — Verification

- [ ] T032 If a permissioned account is available, run NAS/manual smoke for
  summary, positions, exposure, and risk checks.
- [ ] T033 Record verification results and known unavailable broker-permission
  gaps in `specs/014-portfolio-risk-analysis/VERIFICATION.md`.
