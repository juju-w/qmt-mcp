# Tasks: Intelligent Instrument Screening

**Input**: Design documents from
`specs/033-intelligent-instrument-screening/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/screening-tools.md`, and `quickstart.md`

**Tests**: Required by the specification success criteria. Within each story,
write the listed tests first and confirm they fail for the intended reason
before implementing the behavior.

**Format**: `[ID] [P?] [Story] Description with exact file path`

- **[P]**: May run in parallel after its stated dependencies because it edits
  different files.
- **[US1-US4]**: Maps directly to the four user stories in `spec.md`.
- Keep 033 isolated from unrelated 032 changes. Do not add PostgreSQL
  migrations, CLI commands, an MCP App, trading operations, NumPy, or pandas.

## Phase 1: Setup

**Purpose**: Establish the package and deterministic fixture layout without
changing runtime behavior.

- [x] T001 Create the `appliance/mcp/qmt_mcp_screening/` package skeleton with
  `__init__.py`, `models.py`, `catalog.py`, `presets.py`, `exposures.py`,
  `profiles.py`, `validation.py`, `sources.py`, `market_factors.py`,
  `financial_factors.py`, `ranking.py`, `cache.py`, `service.py`, `text.py`, and
  `tools.py`.
- [x] T002 [P] Add deterministic ETF, stock/profile, daily-bar, snapshot, and
  announcement-time financial fixture files under
  `appliance/mcp/tests/fixtures/screening/`, including CSI 500 lookalikes and
  reports announced after the fixture `as_of`.
- [x] T003 [P] Add shared fake source builders and hand-calculated assertion
  helpers in `appliance/mcp/tests/screening_fixtures.py` without importing
  xtquant, NumPy, pandas, MCP, or asyncpg.

**Checkpoint**: Package and fixture paths exist; no tools are registered yet.

---

## Phase 2: Foundational Contracts and Bounds

**Purpose**: Build the typed catalog/request/cache foundation required by every
user story.

**Critical**: Complete this phase before story implementation.

### Tests first

- [x] T004 [P] Add failing enum, `TypedDict`, canonical `FactorRef`, JSON-clean,
  and factor-version tests in
  `appliance/mcp/tests/unit/test_screening_models.py`.
- [x] T005 [P] Add failing tests for all shared/stock/ETF definitions, parameter
  windows, domains, localized labels, profile compatibility, and five preset
  expansions in `appliance/mcp/tests/unit/test_screening_catalog.py`.
- [x] T006 [P] Add failing request tests for invalid factor/window/operator/unit,
  rank-versus-sort conflict, decimal-ratio semantics, missing policies, and
  configured capacity limits in
  `appliance/mcp/tests/unit/test_screening_validation.py`.
- [x] T007 [P] Add failing concurrency, TTL, LRU, factor-key, compact-JSON,
  64-MiB payload-budget, and immutable-read tests in
  `appliance/mcp/tests/unit/test_screening_cache.py`.
- [x] T008 [P] Add failing startup/default/bounds tests for all
  `QMT_SCREEN_*` settings and default Task inclusion in
  `appliance/mcp/tests/unit/test_config.py`.

### Implementation

- [x] T009 Implement dependency-light enums, records, Python 3.11/3.12
  `TypedDict` request shapes, canonical factor references, and observation
  missing reasons in `appliance/mcp/qmt_mcp_screening/models.py`.
- [x] T010 Implement `screening-factors-v1`, all declared factor definitions,
  profile metadata, units, domains, windows, and static availability metadata
  in `appliance/mcp/qmt_mcp_screening/catalog.py`.
- [x] T011 [P] Implement versioned universe/ranking preset expansion with no
  hidden risk-preference inference in
  `appliance/mcp/qmt_mcp_screening/presets.py`.
- [x] T012 Implement pre-scan request normalization and validation, actionable
  valid alternatives, factor-reference limits, and filter/rank/sort contracts
  in `appliance/mcp/qmt_mcp_screening/validation.py`.
- [x] T013 [P] Implement lock-protected bounded factor-observation and compact
  JSON TTL/LRU primitives in `appliance/mcp/qmt_mcp_screening/cache.py`.
- [x] T014 Add validated screening bounds and defaults to
  `appliance/mcp/qmt_mcp_core/config.py`, including
  `qmt_screen_instruments` in `DEFAULT_TASK_TOOLS`.
- [x] T015 Add a plain-Python package import test to
  `appliance/mcp/tests/unit/test_screening_models.py` that fails if any pure
  screening module imports xtquant, NumPy, pandas, MCP, Pydantic, or asyncpg.
- [x] T016 Run the Phase 2 unit files and confirm every foundational contract is
  green before beginning user stories.

**Checkpoint**: Definitions, presets, request validation, bounds, and generic
caches are stable and dependency-light.

---

## Phase 3: User Story 1 - Discover Valid Factors (Priority: P1)

**Goal**: An AI can discover valid stock/ETF factors, profiles, presets,
exposure aliases, ranges, availability, and next steps without guessing.

**Independent Test**: Call `qmt_factor_catalog` on a fake runtime with selected
capabilities missing and verify schema, localization, profile/OAuth visibility,
and truthful availability without any universe scan.

### Tests first

- [x] T017 [P] [US1] Add failing runtime capability-overlay tests for daily
  bars, financial tables, ETF reference data, IOPV, and partial coverage in
  `appliance/mcp/tests/unit/test_screening_catalog.py`.
- [x] T018 [P] [US1] Add failing MCP integration tests for catalog input/output
  schema, read-only annotations, concise text, `full`/`readonly`/`market`
  visibility, custom deny rules, and OAuth market scope in
  `appliance/mcp/tests/integration/test_screening_tools.py`.
- [x] T019 [P] [US1] Add failing docstring tests that require factor discovery,
  profile separation, decimal units, availability, no guessing, and next-tool
  guidance in `appliance/mcp/tests/unit/test_screening_tool_descriptions.py`.

### Implementation

- [x] T020 [US1] Implement active-runtime capability probing and immutable
  availability overlays in `appliance/mcp/qmt_mcp_screening/catalog.py` without
  hiding unavailable P0 definitions.
- [x] T021 [P] [US1] Implement Chinese/English catalog summaries, availability
  counts, and next-step rendering in
  `appliance/mcp/qmt_mcp_screening/text.py`.
- [x] T022 [US1] Implement `qmt_factor_catalog` with the contract docstring,
  typed inputs, structured envelope, audit fields, and text renderer in
  `appliance/mcp/qmt_mcp_screening/tools.py`.
- [x] T023 [US1] Add the screening registration hook to
  `appliance/mcp/qmt_mcp_xtdata/tools.py`, injecting only normalized xtdata/cache
  callables and registering the catalog under family `xtdata`.
- [x] T024 [US1] Run the US1 unit/integration tests and verify catalog calls make
  no bar, financial, snapshot, download, formula, database, or xttrade calls.

**Checkpoint**: US1 works independently. Agents can construct valid requests,
but candidate screening is not yet available.

---

## Phase 4: User Story 2 - Screen a Comparable Universe (Priority: P1)

**Goal**: Resolve one strict stock/ETF universe, compute bounded point-in-time
factors, apply hard filters, and return explainable sorted or ranked results.

**Independent Test**: Run the deterministic CSI 500 ETF and non-financial stock
fixtures through `ScreeningService`; verify membership is resolved before rank,
financial companies do not receive ordinary-company factors, later-announced
reports do not leak, and displayed contributions reconstruct the score.

### Universe tests first

- [x] T025 [P] [US2] Add failing strict ETF exposure tests for aliases,
  canonical IDs, exact-name rules, code-substring rejection, unknown exposure,
  and provenance in `appliance/mcp/tests/unit/test_screening_exposures.py`.
- [x] T026 [P] [US2] Add failing stock-profile tests for exact bank/broker/
  insurer sector sets, safe non-financial residual classification, incomplete
  classifier failure, and profile incompatibility in
  `appliance/mcp/tests/unit/test_screening_profiles.py`.
- [x] T027 [US2] Add failing universe tests for exact codes, exact sectors,
  A-share/all-ETF market sets, deduplication, asset-type filtering, seed-only or
  partial cache policy, and the 5,000-code cap in
  `appliance/mcp/tests/unit/test_screening_universe.py`.

### Universe implementation

- [x] T028 [P] [US2] Implement the reviewed canonical ETF exposure alias catalog
  and strict normalized membership rules in
  `appliance/mcp/qmt_mcp_screening/exposures.py`.
- [x] T029 [P] [US2] Implement versioned stock/ETF profile classification and
  fail-closed financial-sector residual logic in
  `appliance/mcp/qmt_mcp_screening/profiles.py`.
- [x] T030 [US2] Implement `codes`/`sector`/`market`/`exposure` resolution,
  completeness policy, membership digest, and provenance in
  `appliance/mcp/qmt_mcp_screening/service.py` using small resolver collaborators
  from `exposures.py` and `profiles.py`.

### Factor tests first

- [x] T031 [P] [US2] Add hand-calculated failing tests for adjusted returns,
  MA gap/alignment, annualized volatility, max drawdown, trading ratio, average
  and relative amount, turnover, Amihud illiquidity, market value, and peer
  relative strength in
  `appliance/mcp/tests/unit/test_screening_market_factors.py`.
- [x] T032 [P] [US2] Add failing announcement-time timeline tests for report
  cutoff, restatements, annual/YTD TTM assembly, latest balance/capital, and
  duplicate/malformed rows in
  `appliance/mcp/tests/unit/test_screening_financial_timeline.py`.
- [x] T033 [P] [US2] Add failing financial-factor tests for earnings yield, PB,
  ROE, revenue/profit growth, gross margin, CFO/profit, debt/assets, negative
  earnings, zero/sign-changing denominators, and non-financial-only semantics in
  `appliance/mcp/tests/unit/test_screening_financial_factors.py`.

### Factor implementation

- [x] T034 [P] [US2] Implement finite-value/unit normalization and all shared
  market, liquidity, risk, and stock market factors in
  `appliance/mcp/qmt_mcp_screening/market_factors.py`.
- [x] T035 [P] [US2] Implement documented financial-field aliases,
  announcement-time timeline assembly, TTM arithmetic, and all P0 stock
  fundamentals in `appliance/mcp/qmt_mcp_screening/financial_factors.py`.

### Source adapter tests and implementation

- [x] T036 [US2] Add failing source-adapter tests for 50-code daily/snapshot and
  200-code financial batches, `front_ratio` versus unadjusted reads, completed
  bars, source timestamps, malformed broker shapes, call counts, and release of
  raw batch objects in `appliance/mcp/tests/unit/test_screening_sources.py`.
- [x] T037 [US2] Implement immutable `DataContext`, normalized instrument/bar/
  snapshot/financial adapters, staged batching, fresh two-sided spread checks,
  and optional existing-bars-cache reuse in
  `appliance/mcp/qmt_mcp_screening/sources.py`.

### Filter/rank tests and implementation

- [x] T038 [P] [US2] Add failing tests for ordered hard filters, direct sort,
  direction-aware percentiles, conditional 1st/99th winsorization, normalized
  weights, target ranks, coverage, contribution totals, and deterministic tie
  breakers in `appliance/mcp/tests/unit/test_screening_ranking.py`.
- [x] T039 [US2] Implement hard-filter decisions, comparable-universe
  transforms, weighted scores, direct sort, missing-last behavior, coverage,
  contribution rows, and tie breakers in
  `appliance/mcp/qmt_mcp_screening/ranking.py`.

### Service and tool tests first

- [x] T040 [P] [US2] Add a failing end-to-end service test for the CSI 500 ETF
  fixture, proving S&P 500/technology/biotech lookalikes are removed before
  liquidity/spread rank in
  `appliance/mcp/tests/unit/test_screening_service_etf.py`.
- [x] T041 [P] [US2] Add a failing end-to-end stock fixture test proving
  profile isolation, announcement-time cutoff, market gates, financial rank,
  stage counts, source dates, and score reconstruction in
  `appliance/mcp/tests/unit/test_screening_service_stock.py`.
- [x] T042 [P] [US2] Add failing capacity/performance-shape tests proving at most
  260 daily rows per code, bounded batch sizes, expensive data only for
  survivors, at most 24 factor refs, and at most 100 public rows in
  `appliance/mcp/tests/unit/test_screening_service_capacity.py`.
- [x] T043 [US2] Implement staged request orchestration, factor requirement
  unioning, cache lookup/fill, filter short-circuiting, finalist snapshot reads,
  rank/sort execution, stage counts, coverage, warnings, and normalized result
  assembly in `appliance/mcp/qmt_mcp_screening/service.py`.
- [x] T044 [P] [US2] Implement Chinese/English screen summaries limited to ten
  rows and two key factors per row in
  `appliance/mcp/qmt_mcp_screening/text.py`.
- [x] T045 [US2] Add failing integration tests for
  `qmt_screen_instruments` nested schema, validation alternatives, structured/
  text parity, audit fields, profile/OAuth visibility, normal synchronous calls,
  MCP Task interception, cancellation outcome, and no App metadata in
  `appliance/mcp/tests/integration/test_screening_tools.py`.
- [x] T046 [US2] Implement and register `qmt_screen_instruments` with its full
  agent-facing docstring, worker timeout, read-only annotations, text renderer,
  and injected `ScreeningService` in
  `appliance/mcp/qmt_mcp_screening/tools.py` and
  `appliance/mcp/qmt_mcp_xtdata/tools.py`.
- [x] T047 [US2] Run all US2 pure, service, and MCP integration tests and confirm
  a usable screen works without US3 explanation support.

**Checkpoint**: US1+US2 form the usable MVP: discover factors, strictly resolve
the universe, filter, and rank with transparent values and source dates.

---

## Phase 5: User Story 3 - Explain a Captured Result (Priority: P1)

**Goal**: Explain selected, eligible-unselected, and rejected candidates from
the exact captured screen without new market-data calls.

**Independent Test**: Store a deterministic completed result, explain several
candidate states, and prove source call counts remain zero; expire it and verify
the tool requests a rerun rather than recomputing.

### Tests first

- [x] T048 [P] [US3] Add failing compact-result-store tests for random `scr_`
  IDs, immutable JSON payloads, TTL, count/payload eviction, selected and
  rejected candidate retention, and concurrent reads in
  `appliance/mcp/tests/unit/test_screening_cache.py`.
- [x] T049 [P] [US3] Add failing explanation tests for selected,
  eligible-unselected, rejected, unknown-code, unknown-ID, expired-ID, coverage,
  filter trace, rank contributions, and zero source calls in
  `appliance/mcp/tests/unit/test_screening_service.py`.
- [x] T050 [P] [US3] Add failing MCP schema/docstring/text/profile/OAuth tests for
  `qmt_explain_screen_result` in
  `appliance/mcp/tests/integration/test_screening_tools.py` and
  `appliance/mcp/tests/unit/test_screening_tool_descriptions.py`.

### Implementation

- [x] T051 [US3] Implement the compact immutable `ScreenResultStore`, bounded
  candidate explanation projection, random ID generation, and expiry details in
  `appliance/mcp/qmt_mcp_screening/cache.py`.
- [x] T052 [US3] Persist completed captured results after ranking and implement
  source-free candidate lookup/explanation assembly in
  `appliance/mcp/qmt_mcp_screening/service.py`.
- [x] T053 [P] [US3] Implement Chinese/English explanation summaries and
  largest-contribution wording in `appliance/mcp/qmt_mcp_screening/text.py`.
- [x] T054 [US3] Implement and register `qmt_explain_screen_result` with exact
  captured-result semantics and rerun guidance in
  `appliance/mcp/qmt_mcp_screening/tools.py`.
- [x] T055 [US3] Run the US3 unit/integration tests and verify repeated
  explanation does not change timestamps, score, filter decisions, or source
  call counts.

**Checkpoint**: US1-US3 provide factor discovery, screening, and auditable
candidate explanations from one immutable data context.

---

## Phase 6: User Story 4 - Degrade Without Optional Services (Priority: P2)

**Goal**: Current screening works without PostgreSQL and handles missing,
permissioned, stale, partial, and source-error data according to explicit
policy without hidden downloads or substitutions.

**Independent Test**: Run catalog/screen/explain with no DB URL and selectively
missing financial, ETF, IOPV, quote, and cache capabilities; verify successful
eligible paths, fail-closed required paths, neutral optional rank behavior, and
repair guidance.

### Tests first

- [x] T056 [P] [US4] Add failing no-PostgreSQL and database-outage tests proving
  current screen/result explanation remain functional and no DB migration or
  asyncpg import occurs in
  `appliance/mcp/tests/unit/test_screening_no_db.py`.
- [x] T057 [P] [US4] Add failing capability/missing-policy tests for unavailable
  hard filters, optional `exclude`/`neutral`/`fail`, effective-weight changes,
  coverage penalties, partial candidates, and per-candidate source errors in
  `appliance/mcp/tests/unit/test_screening_missing_policy.py`.
- [x] T058 [P] [US4] Add failing freshness tests for stale/locked/crossed/
  one-sided spreads, historical `as_of` snapshot rejection, missing IOPV, and
  cross-border session mismatch in
  `appliance/mcp/tests/unit/test_screening_sources.py`.
- [x] T059 [P] [US4] Add failing call-spy tests proving screening never invokes
  `download_financial_data`, `download_etf_info`, formula, filesystem, network,
  xttrade, or order functions in
  `appliance/mcp/tests/unit/test_screening_side_effects.py`.

### Implementation

- [x] T060 [US4] Complete capability gates, required-versus-optional factor
  planning, negative-cache TTLs, source error isolation, and coverage
  aggregation in `appliance/mcp/qmt_mcp_screening/catalog.py`,
  `sources.py`, and `service.py`.
- [x] T061 [US4] Add explicit existing download-tool repair guidance while
  preserving read-only execution in `appliance/mcp/qmt_mcp_screening/service.py`
  and `text.py`.
- [x] T062 [US4] Add a no-DB fake-runtime integration scenario covering catalog,
  Task screen, explanation, unavailable optional factors, and structured errors
  in `appliance/mcp/tests/integration/test_screening_tools.py`.
- [x] T063 [US4] Run the US4 test matrix and confirm the feature imports and
  operates with `QMT_DB_URL` unset and all P1 ETF capabilities unavailable.

**Checkpoint**: All four user stories are independently covered; optional
infrastructure and permissions cannot break the core current-screen workflow.

---

## Phase 7: Cross-Cutting Contracts and Documentation

**Purpose**: Keep the feature understandable to agents/operators and prevent
regressions outside screening.

- [x] T064 [P] Add a complete tool-description regression matrix for all three
  tools in `appliance/mcp/tests/unit/test_screening_tool_descriptions.py`,
  covering when to use/not use, search-first guidance, asset/profile/exposure
  boundaries, decimal units, point-in-time/freshness, missing data, Tasks, and
  next tools.
- [x] T065 [P] Add existing-tool regression assertions for search, raw bars,
  reference data, formula runtime, tool profiles, OAuth scopes, and K-line App
  metadata in `appliance/mcp/tests/integration/test_app_asgi.py` and
  `appliance/mcp/tests/integration/test_screening_tools.py`.
- [x] T066 [P] Document Chinese discovery/screen/explain examples, factor
  boundaries, private read-only positioning, optional PG, and no automatic
  download behavior in `README.md` and `appliance/README.md`.
- [x] T067 [P] Add the equivalent English documentation in `README.en.md` and
  update host/Task usage in `docs/MCP-CLIENTS.md`.
- [x] T068 Validate every command and expected behavior in
  `specs/033-intelligent-instrument-screening/quickstart.md` against the final
  implementation, correcting the quickstart rather than weakening tests.

**Checkpoint**: Contract, docs, and existing MCP surfaces agree with the
implementation.

---

## Phase 8: Verification and Delivery

**Purpose**: Run all repository gates, record real evidence, and deliver through
the normal PR/release process.

- [x] T069 Run `ruff check`, `ruff format --check`, and all dependency-light
  pytest suites from `appliance/mcp/`; fix failures without broad refactors.
- [x] T070 Run MCP integration tests with the official SDK, including profiles,
  OAuth, Tasks, cancellation, structured/text output, and K-line App regression.
- [x] T071 [P] Run optional PostgreSQL tests, Go test/vet/build/conformance,
  launcher restore/build/test, release-policy tests, actionlint, and packaging
  checks required by `AGENT.md`.
- [x] T072 Run live QMT smoke for one strict ETF exposure and one narrow stock
  universe; when local financial data is present, verify one announcement-time
  stock screen without asserting a golden investment rank.
- [x] T073 Record catalog capabilities, universe provenance, source dates, stage
  counts, rank reconstruction, cache reuse/expiry, no-download call evidence,
  test commands, and any broker limitations in
  `specs/033-intelligent-instrument-screening/VERIFICATION.md`.
- [x] T074 Run `git diff --check`, secret/broker-binary/account/host-data review,
  dependency review, and confirm no PostgreSQL migration, CLI, MCP App, trading,
  NumPy, or pandas scope leaked into 033.
- [x] T075 Update the 033 feature row in `AGENT.md` only after required automated
  and live verification is complete; keep unsupported P1 capabilities described
  as gated rather than implemented everywhere.
- [x] T076 Commit with a Conventional Commit, open a PR from the dedicated 033
  feature branch, and observe every PR check to a terminal green result.
- [ ] T077 Merge only after green CI, then observe main CI and release automation
  to a terminal result and record any release-specific follow-up.

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1** has no dependency.
- **Phase 2** depends on Phase 1 and blocks every user story.
- **US1 (Phase 3)** and the pure US2 tests may begin after Phase 2; US2 tool
  registration reuses the US1 registration boundary.
- **US2 (Phase 4)** depends on foundational catalog/validation/cache contracts,
  not on catalog-tool completion; US1 and most pure US2 work can run in parallel.
- **US3 (Phase 5)** depends on completed US2 captured candidate/result assembly.
- **US4 (Phase 6)** depends on US2 source/service behavior and US3 result cache
  for its full integration scenario.
- **Phases 7-8** depend on all selected user stories.

### Critical path

```text
T001 -> T009-T014 -> T023 -> T030/T034/T035/T037/T039
     -> T043 -> T046 -> T051/T052/T054 -> T060-T062
     -> T068 -> T069-T075 -> T076-T077
```

### User-story independence

- **US1**: Catalog can be called and tested without universe/factor reads.
- **US2**: `ScreeningService` and screen tool return usable results without the
  explanation tool; this plus US1 is the first usable MVP.
- **US3**: Explanation tests can load a captured fixture result and make zero
  xtdata calls.
- **US4**: Degradation tests use a fake runtime with no DB and selectively absent
  capabilities; they do not require live premium data.

### Parallel opportunities

- T002 and T003 can run in parallel after T001 establishes paths.
- T004-T008 are independent failing-test files.
- T011 and T013 can run in parallel after T009; T010/T012 share catalog
  contracts and should be reviewed together.
- T017-T019 can run in parallel before T020-T023.
- T025-T027, T031-T033, and T038 can be authored in parallel after Phase 2.
- T028/T029, T034/T035, and documentation T066/T067 edit disjoint files and can
  run in parallel after their test prerequisites.
- T048-T050 and T056-T059 are parallel test groups.
- T069-T071 may run in parallel only when they use independent build/test
  resources and no shared live QMT session.

## Implementation Strategy

1. Complete Setup and Foundational contracts with green pure tests.
2. Deliver US1 factor discovery and validate agent-facing schema/docstrings.
3. Deliver US2 in vertical slices: strict universe, pure factors, sources,
   ranking, service, then MCP Task tool. Stop and validate the usable MVP.
4. Add US3 immutable explanation without changing captured rank semantics.
5. Add US4 failure/capability hardening without introducing hidden side effects.
6. Update docs, run full/local/live gates, record verification, and use the
   normal PR/release workflow.

## Notes

- Every task checkbox starts unchecked because no 033 implementation exists.
- Tests named "failing" are committed only with the implementation or in a
  deliberate red/green sequence; the final branch must remain green.
- Preserve raw factor values even when the rank transform winsorizes.
- A preset threshold is not a validation bound or investment recommendation.
- Do not mark live/P1 capability work complete using fake data alone.
- Do not switch branches or commit until unrelated dirty 032 work is safely
  separated.
