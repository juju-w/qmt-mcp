# Implementation Plan: Intelligent Instrument Screening

**Branch**: `codex/033-intelligent-instrument-screening` | **Date**:
2026-08-16 | **Spec**:
[spec.md](./spec.md)

**Input**: Feature specification from
`/specs/033-intelligent-instrument-screening/spec.md`

## Summary

Add a dedicated, dependency-light screening domain above existing xtdata,
instrument search, and reference-data adapters. The implementation publishes a
versioned factor catalog; resolves strict stock/ETF universes before ranking;
calculates bounded market and announcement-time financial factors in batches;
applies typed filters and explainable within-universe percentile ranks; and
retains short-lived captured results for exact explanations.

The tools remain in the existing `xtdata` authorization family, use no new
runtime dependency, do not automatically download data, do not place trades,
do not require PostgreSQL, and do not add an MCP App.

## Technical Context

**Language/Version**: Python 3.12 in Docker/Wine and Python 3.11 in the Windows
launcher; Go 1.25/.NET 10 unchanged

**Primary Dependencies**: Python standard library; official MCP Python SDK
2.0.0 through the existing core; broker-supplied `xtquant.xtdata`; existing
`qmt_mcp_xtdata` serializers/search cache; optional existing bars warehouse

**Storage**: Existing instrument JSON cache and optional PostgreSQL bars
warehouse; new bounded in-memory factor-observation and screen-result caches;
no database migration

**Testing**: Dependency-light pytest unit tests; official MCP SDK integration
tests with fake xtdata; existing DB, Go, .NET, release, and policy regression
suites; live QMT smoke for capability/membership/timestamp checks

**Target Platform**: The shared streamable-HTTP MCP server on native Windows
x64 and Linux/amd64 Docker/Wine; text/structured clients with or without MCP
Tasks; no frontend runtime

**Performance Goals**: Factor catalog and cached explanation under 50 ms on the
host unit tier; process up to 5,000 universe members in batches without retaining
the complete raw xtdata object graph; return at most 100 rows; keep screening
cache state bounded and reusable within one completed-session context

**Constraints**: Read-only; broker-agnostic; no hidden data downloads; no
NumPy/pandas dependency; no caller expressions; no cross-asset/profile rank;
point-in-time financial cutoff; fresh-only spread/IOPV; actionable missing and
capacity diagnostics; no App or new PostgreSQL schema

**Scale/Scope**: Two asset types, eleven shared P0 factors, thirteen
stock-specific P0 factors, capability-gated ETF P1 factors, five ranking
presets, three MCP tools, maximum 24 factor references per request, maximum
5,000 candidates, maximum 100 output rows, and a default captured-result cache
bounded by both 100 entries and 64 MiB

## Constitution Check

- **I Broker-agnostic base**: Pass. Factors consume normalized official xtdata
  fields and versioned generic aliases; no broker binary/path/data is added.
- **II Read-only by default**: Pass. All three tools are read-only. Screening
  never calls download APIs, formula mutation, xttrade, or order operations.
- **III Reproducible pinned builds**: Pass. No new dependency is introduced;
  formulas, exposure aliases, presets, and factor version live in tracked code.
- **IV Contract-first MCP**: Pass. Typed nested requests, validation domains,
  structured results, tool descriptions, and examples are specified in
  `contracts/screening-tools.md` before implementation.
- **V Observable and audited**: Pass. Existing registry audit, worker timeout,
  Tasks lifecycle, and structured errors apply; results add stage counts,
  source dates, coverage, factor version, and missing diagnostics.
- **VI Security by default**: Pass. Existing bearer/OAuth market scope and tool
  profiles apply. No filesystem path, code execution, external fetch, account
  data, credential, or write operation is accepted.
- **VII Spec-driven delivery**: Pass. Feature 033 is isolated from the in-flight
  032 code and has spec, research, data model, contracts, quickstart, and plan
  artifacts before tasks/implementation.

Post-design re-check: all gates pass. No constitution exception or complexity
waiver is required.

## Design

### Package and composition

Create `qmt_mcp_screening` as a sibling domain package. Its pure modules do not
import MCP, xtquant, pandas, NumPy, or asyncpg. `tools.py` is the only MCP
registration boundary; `sources.py` is the only xtdata-facing domain adapter.

At the end of existing xtdata registration, construct one `ScreeningService`
and pass it validated callables for:

- Exact xtdata calls.
- Existing normalized daily-bars reads.
- Instrument cache/status access.
- Existing normalized snapshot/reference serializers.

Register the tools with `family="xtdata"`, read-only behavior, market OAuth
scope, existing visibility policy, worker backing, and concise text renderers.
Add only `qmt_screen_instruments` to `DEFAULT_TASK_TOOLS`.

Use standard-library `TypedDict` input annotations for nested universe, filter,
rank, and sort objects so MCP emits useful schemas without adding a direct
Pydantic dependency to the plain-host unit tier. On Python 3.11, use the already
available `typing_extensions.TypedDict`; on Python 3.12, use `typing.TypedDict`.
All values pass a second explicit domain validator before any universe scan.

### Catalog and presets

`catalog.py` owns immutable `FactorDefinition` records, profile definitions,
parameter domains, validation domains, source/freshness metadata, and
`screening-factors-v1`. `presets.py` owns versioned, fully expandable universe
and ranking presets. Runtime capability probes overlay availability but never
delete the definition from the default catalog.

Each factor calculator is registered by stable factor ID and advertises its
input requirements. The service computes the union of required fields and
windows once per request, rather than making one source call per factor.

### Universe resolution and classification

`UniverseResolver` accepts only the four declared universe kinds:

- `codes`: exact validated QMT codes.
- `sector`: exact official sector names and memberships.
- `market`: supported aliases such as A-share or all ETF, backed by exact sector
  sets rather than fuzzy text.
- `exposure`: known canonical ETF exposure ID/alias resolved from official
  metadata/sector evidence first and strict tracked aliases second.

The 006 cache supplies names, types, listing metadata, and stable source state.
Seed-only or partial cache state is visible. `require_complete` fails when the
resolver cannot establish complete membership; `allow_partial` continues with
an explicit warning and cannot make an unqualified "best in exposure" claim.

`exposures.py` contains a small reviewed alias catalog for common exposures and
strict normalized-name rules. Code substrings never establish membership. The
catalog is additive and versioned independently from fuzzy aliases.

`profiles.py` resolves bank, broker, and insurer membership from exact official
sector sets. `non_financial` is the residual only if all special-financial sets
were loaded successfully. Otherwise ordinary-company fundamental requests fail
closed for unclassified candidates.

### Source capture and batching

`sources.py` creates one immutable `DataContext` and captures source data in
stages:

1. Resolve at most `QMT_SCREEN_MAX_UNIVERSE_CODES` (default 5,000).
2. Read instrument metadata and apply profile/data-quality gates.
3. Read up to 260 completed daily observations in batches of at most 50 codes,
   with `front_ratio` for return/risk calculations and required unadjusted
   closes separately for market values.
4. Apply shared/market hard filters and release raw batch rows.
5. If required, read Balance, Income, CashFlow, Capital, and Pershareindex in
   announcement-time mode for surviving stocks, at most 200 codes per call.
6. If requested, fetch current snapshots in batches of 50 only for surviving
   candidates; validate quote timestamp, market state, and two-sided prices.
7. Fetch IOPV/ETF reference data only when the runtime advertises the required
   capability and the factor is requested.

The screen never invokes explicit download functions. Missing locally cached
financial/ETF data returns the existing download tool as next-step guidance.

### Market factors

`market_factors.py` contains pure numeric functions over normalized completed
daily series. It computes shared returns, moving-average gap/alignment,
volatility, drawdown, average/relative amount, trading ratio, and stock turnover,
Amihud illiquidity, and peer-relative strength.

Calculators return `FactorObservation`, not bare numbers. Invalid prices,
insufficient history, suspension gaps, unit uncertainty, and non-finite outputs
become typed missing observations. Unit normalization for volume and share
counts is centralized and covered by broker-shape fixtures before turnover or
market value is reported.

### Point-in-time fundamentals

`financial_factors.py` first builds a normalized per-code financial timeline:

- Map documented field aliases in one reviewed table.
- Parse report period and announcement time.
- Exclude rows announced after `as_of`.
- Retain the latest announced revision per report period.
- Build TTM cumulative values from current YTD, prior fiscal year, and prior
  comparable YTD, or use the latest fiscal-year value.
- Select the latest announced balance/capital observation for point-in-time
  stock and share values.

Pure calculators then derive earnings yield, PB, ROE, year-over-year revenue and
profit growth, gross margin, cash-flow quality, debt/assets, and market values.
Sign-changing or non-positive required denominators return typed missing
reasons, not extreme values.

### Filtering and ranking

`validation.py` canonicalizes factor refs and checks asset/profile compatibility,
parameters, operators, domains, request conflicts, missing policies, and limits
before expensive reads.

`ranking.py`:

1. Applies hard filters in normalized request order.
2. Builds cross-sectional distributions only from available observations in the
   remaining comparable universe.
3. Winsorizes the transform at disclosed 1st/99th percentiles only when sample
   size is sufficient; raw values remain unchanged.
4. Converts values to direction-aware percentiles.
5. Normalizes positive requested weights and applies the declared optional-rank
   missing policy.
6. Produces score `[0,100]`, contribution rows, coverage, and deterministic tie
   breakers.

Direct sort bypasses composite scoring but still places missing values last and
uses stable tie breakers. No fuzzy relevance or code text enters either path.

### Captured results and cache

`cache.py` provides lock-protected bounded TTL/LRU stores:

- Factor observations keyed by broker, factor version, code, as-of session,
  adjustment, factor ID, and canonical parameters. Daily/financial values may
  be reused only for the same source date and version; snapshot entries use a
  short freshness bound.
- Screen results keyed by a random `scr_` ID and stored as immutable compact
  JSON bytes, with default TTL 900 seconds, default maximum 100, and default
  total payload budget 64 MiB. Stored details are bounded by the request
  universe maximum and contain no account or credential data.

`qmt_explain_screen_result` reads this immutable captured result and never calls
sources. Expired IDs return a rerun instruction. PostgreSQL is not changed; a
future factor-snapshot feature can implement a persistence interface without
changing the public screening contract.

### Text and structured output

`text.py` provides localized `zh-CN`/English renderers:

- Catalog: count, availability summary, profile/preset guidance.
- Screen: universe/source dates, stage counts, at most ten rows with two key
  factors, coverage/warnings, and explanation next step.
- Explanation: pass/fail summary and largest disclosed contributions.

The full result stays in `structuredContent`; no successful tool returns only a
large JSON text dump or UI metadata. No App extension/resource is registered.

### Configuration

Add validated `CoreConfig` values with conservative defaults:

```text
QMT_SCREEN_MAX_UNIVERSE_CODES=5000
QMT_SCREEN_MAX_FACTOR_REFS=24
QMT_SCREEN_MAX_RESULTS=100
QMT_SCREEN_RESULT_TTL_SECONDS=900
QMT_SCREEN_RESULT_CACHE_MAX=100
QMT_SCREEN_RESULT_CACHE_MAX_BYTES=67108864
QMT_SCREEN_FACTOR_CACHE_MAX=50000
```

Internal source batch limits remain code-owned at 50 market/snapshot codes and
200 financial codes to match current adapters. Configuration errors fail at
startup and never enlarge limits silently.

## Verification Strategy

### Pure unit tests

- Definition, preset, canonical factor-ref, profile, and exposure catalogs.
- All market and financial formulas with hand-calculated vectors.
- Announcement-time cutoff and TTM assembly across quarter/annual/restatement
  cases.
- Validation domains/operators, filter ordering, rank math, missing policies,
  tie breakers, and score-contribution equality.
- TTL/LRU eviction, immutable captured explanation, and concurrent cache access.
- No third-party imports in pure modules.

### Tool and protocol integration

- Fake xtdata adapter with mixed return shapes, source failures, permission
  absence, partial coverage, stale quotes, and exact call-count assertions.
- Input/output schemas, rich docstrings, structured/text parity, annotations,
  profiles, OAuth scopes, audits, worker timeouts, and MCP Task interception.
- Regression checks for existing search, bars, reference, formula, and K-line
  App tools.

### Live smoke

- Catalog capability truthfulness on the current broker runtime.
- Strict ETF exposure membership before ranking.
- Current narrow stock/ETF screens with source dates and repeat-cache behavior.
- Optional financial screen only when local announcement-time data is present.
- Explanation performs no xtdata calls and expires at the declared TTL.

Live market values are not golden assertions. Tests verify membership,
provenance, point-in-time cutoff, factor arithmetic, rank reconstruction, and
contract behavior.

## Project Structure

```text
specs/033-intelligent-instrument-screening/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── screening-tools.md

appliance/mcp/qmt_mcp_screening/
├── __init__.py
├── models.py              # stdlib typed records and request shapes
├── catalog.py             # immutable factor definitions/capability overlay
├── presets.py             # versioned universe/ranking presets
├── exposures.py           # strict ETF exposure aliases/membership rules
├── profiles.py            # stock/ETF profile classification
├── validation.py          # request/factor/operator/domain validation
├── sources.py             # normalized staged xtdata data access
├── market_factors.py      # pure market/liquidity/risk calculations
├── financial_factors.py   # PIT timeline and pure stock fundamentals
├── ranking.py             # filters, percentiles, scores, tie breakers
├── cache.py               # bounded factor/result TTL-LRU stores
├── service.py             # orchestration and captured result lifecycle
├── text.py                # zh-CN/en concise fallback renderers
└── tools.py               # three MCP registration functions

appliance/mcp/qmt_mcp_core/
├── config.py              # screening bounds + Task default
└── app.py                 # unchanged composition shape; optional registration hook

appliance/mcp/qmt_mcp_xtdata/
├── tools.py               # construct/register ScreeningService after xtdata
├── search_cache.py        # reused instrument metadata/universe cache
├── serializers.py         # reused bars/snapshot normalization
└── reference_serializers.py

appliance/mcp/tests/unit/
├── test_screening_models.py
├── test_screening_catalog.py
├── test_screening_validation.py
├── test_screening_cache.py
├── test_screening_exposures.py
├── test_screening_profiles.py
├── test_screening_universe.py
├── test_screening_market_factors.py
├── test_screening_financial_*.py
├── test_screening_sources.py
├── test_screening_ranking.py
├── test_screening_service_*.py
└── test_screening_tool_descriptions.py

appliance/mcp/tests/integration/
└── test_screening_tools.py

appliance/mcp/tests/fixtures/screening/
└── *.json

README.md
README.en.md
appliance/README.md
docs/MCP-CLIENTS.md
```

**Structure Decision**: Keep factor/ranking logic in a separate pure package,
reuse xtdata only through injected normalized adapters, and retain the existing
family/profile/auth model. This limits changes to core composition and avoids a
second service, data store, formula runtime, frontend, or CLI command tree.

## Complexity Tracking

No constitution violations. The dedicated domain package has multiple small
modules because universe membership, point-in-time accounting, numeric factor
calculation, ranking, and MCP registration have distinct invariants and test
fixtures. Combining them would not remove behavior; it would only hide those
boundaries inside one large tools module.
