# Feature Specification: Intelligent Instrument Screening

**Feature Branch**: `codex/033-intelligent-instrument-screening`

**Created**: 2026-08-16

**Status**: Draft

**Input**: Add asset-aware, explainable screening tools so an AI can discover
and rank suitable A-share stocks or exchange-traded funds without knowing
factor formulas, instrument codes, or QMT data boundaries in advance.

**Depends on**: 003 (xtdata market data), 006 (instrument discovery), 012
(optional PostgreSQL persistence), 016 (reference and financial data), 020
(tool contracts and profiles), and 029 (MCP 2026-07-28 baseline).

## Summary

Add a read-only screening layer above the existing xtdata tools. The layer
publishes a bounded factor catalog, validates a structured screening request,
computes only declared factors, ranks instruments within comparable asset
groups, and explains why each result passed or ranked highly.

The first release is intentionally not a technical-indicator library or a
universal alpha model. It covers A-share stocks and exchange-traded funds with
separate factor profiles. It emphasizes data quality, liquidity, risk, trend,
and a small set of point-in-time stock fundamentals. ETF benchmark and IOPV
factors degrade by capability. Convertible bonds and options require separate
future catalogs.

The feature is designed for less-capable or hallucination-prone agents:

1. The agent discovers valid factor IDs and ranges before screening.
2. Unknown factors, windows, operators, and asset combinations fail with valid
   alternatives instead of being guessed or silently coerced.
3. The server, not the agent, owns formulas, adjustment rules, comparable-peer
   grouping, missing-value policy, and point-in-time financial semantics.
4. Tool descriptions teach the search, screen, inspect, and explain workflow.

## User Scenarios & Testing

### User Story 1 - Discover valid factors before screening (Priority: P1)

An agent receives a request such as "find liquid, profitable A-share companies"
or "find trade-friendly CSI 500 ETFs" but does not know which factors QMT can
provide. It asks for the factor catalog for the requested asset type and gets
typed factor definitions, valid windows, availability, freshness, direction,
and examples.

**Why this priority**: A discoverable contract is the primary defense against
invented factor names, invalid ranges, and accidental cross-asset comparisons.

**Independent Test**: Call `qmt_factor_catalog` for `stock` and `etf` against a
runtime with selected capabilities missing, then verify the catalog remains
complete while accurately marking unavailable factors.

**Acceptance Scenarios**:

1. **Given** `asset_type=stock`, **when** the catalog is requested, **then** it
   returns shared market factors and stock-specific size, value, quality,
   growth, and balance-sheet factors with machine-readable metadata.
2. **Given** `asset_type=etf`, **when** the catalog is requested, **then** it
   returns shared market factors plus conditional benchmark, tracking, IOPV,
   and component factors.
3. **Given** IOPV or ETF component data is unavailable, **when** the catalog is
   requested, **then** the corresponding factors remain discoverable but are
   marked unavailable with a reason and capability requirement.
4. **Given** an unknown asset type or profile, **when** the catalog is
   requested, **then** the response lists the valid types and profiles without
   selecting one on the agent's behalf.

---

### User Story 2 - Screen a comparable instrument universe (Priority: P1)

An agent translates natural-language conditions into a strict screening
request, filters the selected universe, and receives bounded results ranked
only against economically comparable peers.

**Why this priority**: This is the minimum useful intelligent-screening flow and
directly prevents broad fuzzy-search recall from becoming an investment rank.

**Independent Test**: Screen deterministic fixture universes containing
lookalike names, mixed asset classes, missing fundamentals, suspended symbols,
and multiple ETF exposures; verify membership, order, diagnostics, and
provenance.

**Acceptance Scenarios**:

1. **Given** an ETF request for the CSI 500 exposure, **when** liquidity ranking
   runs, **then** S&P 500, technology, biotech, and code-only `500` lookalikes
   are excluded before ranking.
2. **Given** multiple ETFs tracking the same exposure, **when** a trade-friendly
   preset runs, **then** recent amount, usable spread, listing history, and data
   coverage influence rank with every contribution exposed.
3. **Given** an A-share stock request, **when** fundamental ranking runs,
   **then** non-financial companies are not ranked against banks, brokers, or
   insurers under the same fundamental model.
4. **Given** valid hard filters and no rank expression, **when** screening runs,
   **then** results have a deterministic explicit sort and are not assigned an
   opaque AI score.
5. **Given** an invalid factor, window, operator, or value type, **when** the
   request is validated, **then** no scan starts and the error returns valid
   alternatives.

---

### User Story 3 - Understand why an instrument was selected (Priority: P1)

After a screen, the agent or user asks why one candidate ranked above another.
The explanation reports the candidate's raw values, comparable-universe
percentiles, filter decisions, weighted contributions, missing factors, data
dates, and caveats.

**Why this priority**: Explainability lets the agent distinguish a strong result
from one that merely survived missing data or a narrow universe.

**Independent Test**: Explain a selected, rejected, partially scored, and stale
candidate from a deterministic screen result.

**Acceptance Scenarios**:

1. **Given** a valid `screen_id` and instrument code, **when** explanation is
   requested, **then** the response reconstructs each filter and rank
   contribution without recomputing with different market data.
2. **Given** an optional factor was missing and treated neutrally, **when** the
   result is explained, **then** the missing value, policy, coverage effect, and
   reduced confidence are explicit.
3. **Given** an expired screen result, **when** explanation is requested,
   **then** the tool asks the agent to rerun the original request rather than
   explaining a newly computed result as if it were identical.

---

### User Story 4 - Operate without optional persistence or premium data (Priority: P2)

A private QMT-MCP deployment can perform a current screen using xtdata and
bounded in-memory caches. PostgreSQL improves historical reproducibility and
backtesting but is not required for the initial current-state workflow.

**Why this priority**: The personal-appliance deployment must remain useful on
simple Windows and Docker installations.

**Independent Test**: Run a current screen with no database URL and with
permissioned ETF/fundamental capabilities selectively unavailable.

**Acceptance Scenarios**:

1. **Given** no PostgreSQL connection, **when** a current screen runs, **then**
   it succeeds with an in-memory result cache and clearly states that historical
   factor snapshots are not persisted.
2. **Given** a requested factor is unavailable, **when** it is required by a
   hard filter, **then** the request fails closed before returning candidates.
3. **Given** an unavailable optional rank factor, **when** the caller explicitly
   permits partial ranking, **then** results expose factor and candidate
   coverage and never silently substitute another metric.

## Asset Scope and Comparable Universes

`asset_type` is mandatory. Ranking across asset types is prohibited.

### Stock Profiles

| Profile | Initial support | Comparable-universe rule |
|---|---|---|
| `non_financial` | Full P0 market and fundamental factors | Rank within explicit sector, index, or caller-selected universe |
| `bank` | Shared market, liquidity, and risk factors only | Never apply ordinary-company margin, cash-flow, or leverage scoring |
| `broker` | Shared market, liquidity, and risk factors only | Keep separate from banks and ordinary companies |
| `insurer` | Shared market, liquidity, and risk factors only | Keep separate from banks and ordinary companies |

Dedicated financial-industry fundamental factors are deferred. When the stock
profile cannot be classified reliably, fundamental presets MUST fail closed or
require caller clarification; they MUST NOT assume `non_financial`.

### ETF Profiles

| Profile | Initial support | Comparable-universe rule |
|---|---|---|
| `broad_market_equity` | Full shared factors; benchmark factors when mapped | Same underlying index or declared exposure group |
| `sector_theme_equity` | Full shared factors; benchmark factors when mapped | Same sector/theme exposure group |
| `strategy_equity` | Full shared factors; benchmark factors when mapped | Same strategy family, such as dividend or growth |
| `cross_border_equity` | Full shared factors; benchmark factors when mapped | Same overseas index/exposure; account for quote-time differences |
| `bond` | Shared factors only | Same bond category and duration profile when known |
| `commodity` | Shared factors only | Same commodity exposure |
| `money_market` | Shared liquidity and risk factors only | Same money-market category |

ETF fuzzy name or code similarity is never sufficient to establish an
`exposure_group`. A resolved mapping, sector membership, instrument metadata,
or explicit caller constraint is required. Unknown exposure groups may be
filtered but MUST NOT receive a "best ETF for this exposure" rank.

## Factor Catalog

The catalog below defines semantics, not a promise that every broker runtime
has every source field. Each factor reports `availability` as `available`,
`partial`, `unavailable`, or `unknown` for the active runtime.

### Shared P0 Factors

| Factor ID | Parameters | Value type/unit | Definition and use |
|---|---|---|---|
| `is_trading` | none | boolean | Trading state in the captured as-of context; current instrument status or historical suspension flag |
| `listing_days` | none | integer days | Calendar days from official open/listing date to the captured as-of date |
| `trading_ratio` | `window=60` | ratio `[0,1]` | Valid, non-suspended daily observations divided by expected sessions |
| `avg_amount` | `window=20|60` | CNY, non-negative | Mean daily transaction amount over completed sessions |
| `amount_ratio` | `window=20` | ratio, non-negative | Latest completed daily amount divided by the preceding-window mean |
| `bid_ask_spread_bps` | none | bps, non-negative | `(ask1-bid1)/mid*10000`; valid only for fresh, positive two-sided quotes |
| `return` | `window=5|20|60|120` | ratio `[-1,+inf)` | Adjusted-close total price return for trend and relative strength |
| `ma_gap` | `window=20|60|120` | finite ratio | Adjusted close divided by adjusted moving average minus one |
| `ma_alignment` | none | enum | `bullish`, `bearish`, or `mixed` from close, MA20, MA60, and MA120 |
| `annualized_volatility` | `window=20|60` | ratio, non-negative | Daily adjusted-return standard deviation annualized with 252 sessions |
| `max_drawdown` | `window=20|60|250` | ratio `[-1,0]` | Worst adjusted-close decline from a running peak in the window |

Intraday partial bars MUST NOT be compared with completed daily observations as
if they had equal duration. Snapshot spread includes a quote timestamp and
freshness state; stale, locked, crossed, or one-sided quotes produce a missing
factor rather than zero cost.

### Stock-Specific Factors

| Factor ID | Priority | Value type/unit | Definition and use |
|---|---|---|---|
| `float_market_cap` | P0 | CNY, non-negative | Unadjusted as-of close times the latest free-float shares announced by that as-of |
| `total_market_cap` | P0 | CNY, non-negative | Unadjusted as-of close times the latest total shares announced by that as-of |
| `turnover_rate` | P0 | ratio, non-negative | Normalized traded shares divided by free-float shares; 20/60-day aggregation |
| `amihud_illiquidity` | P0 | non-negative scaled ratio | Mean `abs(daily_return)/amount_cny`; scale and window are returned in metadata |
| `sector_relative_strength` | P0 | finite ratio | Stock return minus median return of its declared comparable peer group; 20/60 days |
| `earnings_yield_ttm` | P0 | finite ratio | Point-in-time TTM attributable earnings divided by market value |
| `pb_mrq` | P0 | finite number | Market value divided by latest announced attributable equity |
| `roe_ttm` | P0 | finite ratio | Point-in-time TTM attributable profit relative to average equity |
| `revenue_growth_yoy` | P0 | finite ratio or missing | Like-period revenue growth; non-comparable denominator returns missing |
| `net_profit_growth_yoy` | P0 | finite ratio or missing | Like-period attributable-profit growth; sign-crossing denominator returns missing |
| `gross_margin_ttm` | P0 | finite ratio | TTM gross profit divided by TTM revenue for non-financial companies |
| `cfo_to_net_profit_ttm` | P0 | finite ratio or missing | TTM operating cash flow divided by positive TTM attributable profit |
| `debt_to_assets` | P0 | ratio, normally `[0,1]` | Latest announced total liabilities divided by total assets |
| `asset_growth_yoy` | P1 | finite ratio | Year-over-year total-asset growth; deferred until historical assembly is proven |

Negative earnings are valid observations but are excluded from presets that
claim to rank positive earnings yield. Growth across zero and cash-flow quality
with non-positive profit are not represented as extreme numeric values.

### ETF-Specific Factors

Shared trend, risk, liquidity, listing-history, and spread factors form the ETF
P0. The following factors are conditional because benchmark mapping, IOPV, or
component coverage differs by terminal and permission level.

| Factor ID | Priority | Value type/unit | Definition and capability rule |
|---|---|---|---|
| `benchmark_relative_return` | P1 | finite ratio | ETF return minus mapped benchmark return; 20/60 days |
| `benchmark_correlation` | P1 | ratio `[-1,1]` | Return correlation with mapped benchmark; 60/120 days |
| `tracking_error` | P1 | ratio, non-negative | Annualized standard deviation of ETF-minus-benchmark daily return; 60/120 days |
| `premium_to_iopv` | P1 | finite ratio | Fresh market price divided by fresh IOPV minus one |
| `abs_premium_to_iopv` | P1 | ratio, non-negative | Absolute premium/discount magnitude for ranking execution quality |
| `top10_component_weight` | P1 | ratio `[0,1]` | Concentration of the ten largest available component weights |
| `effective_component_count` | P1 | number `[1,+inf)` | Inverse Herfindahl concentration when component weights are available |
| `portfolio_overlap` | P1 | ratio `[0,1]` | Weighted holding overlap between two comparable ETFs |

ETF fee, official AUM, tracking-difference history, and provider metadata are
not P0 because the current xtdata contract does not guarantee complete,
consistent coverage. They require a separately governed source before use.

## Factor Types, Validation Domains, and Operators

Validation domains protect the contract from impossible values. They are not
investment recommendations and MUST remain separate from preset thresholds.

| Value type | Contract representation | Valid domain | Allowed operators |
|---|---|---|---|
| Ratio/percentage | JSON number; `0.10` means 10% | Factor-specific finite domain | `gt`, `gte`, `lt`, `lte`, `between` |
| Currency | JSON number in CNY | Non-negative finite number | `gt`, `gte`, `lt`, `lte`, `between` |
| Basis points | JSON number | Non-negative finite number | `gt`, `gte`, `lt`, `lte`, `between` |
| Integer days/count | JSON integer | Factor-specific non-negative domain | `eq`, `gt`, `gte`, `lt`, `lte`, `between` |
| Boolean | JSON boolean | `true` or `false` | `eq`, `ne` |
| Enum | JSON string | Catalog-declared values | `eq`, `ne`, `in`, `not_in` |

Narrow empirical thresholds MUST NOT be hard-coded as validation limits.
Financial growth and valuation factors may legitimately exceed common display
ranges. The server rejects NaN and infinity, retains valid outliers in raw
output, and may winsorize only the cross-sectional rank transform with the
chosen bounds disclosed.

Every factor definition includes:

- `factor_id`, localized label, and agent-facing description.
- `asset_types` and compatible profiles.
- `value_type`, `unit`, valid domain, allowed operators, and rank direction.
- Allowed windows and defaults, with no silent fallback for an invalid window.
- `source_class`: `native`, `derived`, `permissioned`, or `external`.
- `freshness`: `snapshot`, `completed_daily`, or `announced_financial`.
- `point_in_time`, `adjustment`, `nullable`, and missing-reason semantics.
- Active-runtime availability, required capability, and coverage estimate.
- Formula version and enough provenance to reproduce the value.

## Presets

Presets are named, versioned starting points. They are fully expanded into the
response so an agent and user can inspect every condition. A caller may override
them explicitly; the server never changes a preset based on an inferred risk
preference.

### Universe Presets

| Preset ID | Default gates |
|---|---|
| `stock_research` | Trading; non-financial profile when fundamentals are used; listing days `>=250`; 60-day average amount `>=CNY 30m`; float market cap `>=CNY 5bn`; 60-day trading ratio `>=0.85` |
| `stock_trade_friendly` | Trading; listing days `>=365`; 60-day average amount `>=CNY 50m`; float market cap `>=CNY 8bn`; at least 50 valid observations in 60 expected sessions |
| `etf_research` | Trading; known ETF profile; listing days `>=120`; 20-day average amount `>=CNY 50m` |
| `etf_trade_friendly` | Trading; known exposure group; listing days `>=250`; 20-day average amount `>=CNY 100m`; fresh spread used for rank when available |

Spread is not a default hard filter because a pre-open, closed-market, stale,
or one-sided quote is not comparable with a fresh continuous-auction quote.

### Ranking Presets

| Preset ID | Asset scope | Declared intent |
|---|---|---|
| `etf_rotation` | Equity ETFs within one exposure-comparable universe | Combine 20/60/120-day momentum, trend, volatility, drawdown, and liquidity |
| `etf_execution_quality` | ETFs within one exposure group | Prefer amount, fresh narrow spread, listing history, and optionally tracking quality |
| `stock_industry_strength` | Stocks within declared peer groups | Combine peer-relative strength, trend, liquidity, stability, and an overheat penalty |
| `stock_liquid_quality` | Non-financial stocks | Combine positive earnings yield, ROE, cash-flow quality, leverage, liquidity, and data coverage |
| `stock_low_vol_value` | Non-financial stocks | Combine positive earnings yield/PB with lower volatility and drawdown |

No preset is named `best`, and no preset claims future return. Raw stock
momentum across the entire A-share market is not a default standalone model;
stock momentum is peer-relative or one disclosed component of a broader rank.

## Screening Request and Ranking Semantics

A screening request contains:

- Required `asset_type` and an explicit or resolved comparable universe.
- Optional asset profile, sector/index membership, ETF exposure group, and
  named preset.
- Optional `as_of`; absent means latest available data with each source date
  reported, not an implied single real-time timestamp.
- Typed hard filters with factor ID, parameters, operator, and value(s).
- An explicit ordered sort or weighted rank expression.
- `missing_policy`: `exclude`, `neutral`, or `fail`, subject to the rules below.
- Bounded `limit`, output fields, and diagnostic detail level.

The execution order is fixed:

1. Resolve and validate the universe without fuzzy-ranking leakage.
2. Apply asset/profile compatibility and data-quality gates.
3. Compute required factors against one captured data snapshot/as-of context.
4. Apply hard filters.
5. Transform optional rank factors within the remaining comparable universe.
6. Combine disclosed contributions, apply deterministic tie breakers, and
   return bounded results plus coverage diagnostics.

Weighted multi-factor ranks use comparable-universe percentiles with declared
direction and disclosed winsorization, not incomparable raw units. The response
returns raw value, transformed percentile, effective weight, and contribution.
If coverage changes effective weights, the normalized weights are also shown.

Required hard-filter factors never use neutral missing values. `neutral` is
allowed only for optional rank factors and produces a coverage penalty. The
default is `exclude` for required filters and optional ranks unless a preset
explicitly declares another behavior. `fail` rejects the complete request when
any candidate lacks a required value.

## Requirements

### Functional Requirements

- **FR-001**: The server MUST expose `qmt_factor_catalog`,
  `qmt_screen_instruments`, and `qmt_explain_screen_result` when xtdata is
  enabled and the active profile permits market-data tools.
- **FR-002**: Every screen MUST require `asset_type=stock|etf`; the server MUST
  reject cross-asset ranking.
- **FR-003**: The server MUST enforce stock and ETF profile compatibility and
  MUST NOT apply ordinary-company fundamental models to banks, brokers, or
  insurers.
- **FR-004**: ETF selection that claims to identify the best product for an
  exposure MUST require a known exposure group before ranking.
- **FR-005**: The catalog MUST expose all metadata defined in the Factor Types
  section and runtime-specific availability without hiding unavailable factors.
- **FR-006**: The P0 implementation MUST cover all shared P0 factors and all
  stock-specific P0 factors whose required official fields pass capability and
  point-in-time tests.
- **FR-007**: P1 ETF and asset-growth factors MUST remain capability-gated and
  MUST NOT be simulated from unrelated fields when unavailable.
- **FR-008**: Financial factors MUST use information available by announcement
  time. Historical `as_of` screens MUST NOT use a report before its announcement
  timestamp.
- **FR-009**: Return, moving-average, volatility, drawdown, and relative-strength
  factors MUST use one declared adjusted-price convention. Market-cap and
  snapshot execution factors MUST use normalized unadjusted current values.
- **FR-010**: The request schema MUST validate factor compatibility, windows,
  operators, units, finite values, bounds, and request size before reading a
  full universe.
- **FR-011**: Invalid requests MUST return actionable valid factor IDs, windows,
  profiles, or operators and MUST NOT silently rename or substitute a factor.
- **FR-012**: Universe resolution MUST be separate from ranking so fuzzy
  instrument-search relevance or code substrings cannot leak into factor rank.
- **FR-013**: Ranking MUST occur within the declared comparable universe and
  MUST expose raw values, percentiles, weights, contributions, tie breakers,
  and candidate coverage.
- **FR-014**: Every result MUST include `screen_id`, normalized request,
  universe definition, candidate counts by stage, data source dates,
  `factor_version`, availability diagnostics, missing reasons, and warnings.
- **FR-015**: Explanations MUST refer to the captured screen result. They MUST
  not silently recompute with newer market data.
- **FR-016**: Screen-result caching MUST be bounded and have an explicit TTL.
  PostgreSQL MAY persist reproducible factor snapshots but MUST NOT be required
  for current screening.
- **FR-017**: Stable instrument metadata and completed daily factor inputs MAY
  be cached. Snapshot spread and IOPV factors MUST honor freshness and MUST NOT
  be served as current after their declared expiry.
- **FR-018**: The implementation MUST bound universe size, factor count,
  historical observations, output rows, concurrent computations, timeout, and
  cache memory; rejected limits MUST report configured maxima.
- **FR-019**: One candidate failure MUST produce bounded partial diagnostics
  when policy permits; it MUST NOT erase successful candidates or expose raw
  proprietary SDK objects.
- **FR-020**: All three tool descriptions/docstrings MUST explain when to use
  the tool, when not to use it, required asset grouping, factor discovery,
  point-in-time and freshness semantics, missing data, output interpretation,
  and the recommended next tool. One-line descriptions are insufficient.
- **FR-021**: Tools MUST be read-only, idempotent for one captured data context,
  audited, worker-backed, and protected by existing authorization, timeout, and
  structured-error contracts.
- **FR-022**: Responses MUST provide concise text guidance and matching
  `structuredContent`; the first implementation MUST remain useful on hosts
  without MCP Apps support.
- **FR-023**: The screen MUST NOT call arbitrary formulas, execute caller code,
  accept filesystem paths, fetch ungoverned internet data, or place/cancel
  orders.
- **FR-024**: Existing search, quote, bars, reference-data, formula, K-line App,
  and trade tools MUST remain backward compatible.

### Proposed Tool Catalog

- `qmt_factor_catalog`: Discover valid factors, presets, profiles, windows,
  types, ranges, availability, freshness, and example screen fragments.
- `qmt_screen_instruments`: Resolve a bounded comparable universe, apply typed
  filters, rank candidates, and return an explainable captured result.
- `qmt_explain_screen_result`: Explain one selected or rejected instrument from
  a non-expired captured screen without changing its data context.

### Key Entities

- **FactorDefinition**: Stable factor ID, compatible assets/profiles, value
  contract, parameters, formula version, source, freshness, availability, and
  missing-value semantics.
- **ScreenUniverse**: Asset type, profile, membership constraints, ETF exposure
  group or stock peer group, and resolution provenance.
- **ScreenFilter**: Factor reference, parameters, typed operator, and value(s).
- **RankComponent**: Factor reference, direction, weight, transform,
  winsorization, and missing-value policy.
- **ScreenRequest**: Universe, as-of context, preset expansion, filters, rank or
  sort, limits, and requested diagnostics.
- **FactorObservation**: Raw value, source timestamp, report/announcement date
  where applicable, adjustment, availability, and missing reason.
- **ScreenResult**: Captured query identity, normalized request, stage counts,
  ranked candidates, diagnostics, provenance, version, and expiry.
- **CandidateExplanation**: Filter decisions, raw and transformed factors,
  contributions, coverage, warnings, and rejection reason for one instrument.

## Edge Cases

- A security name, code, or alias resembles an index exposure but belongs to a
  different ETF or instrument type.
- One ETF has a fresh quote while another has only a previous-close snapshot.
- Cross-border ETF and overseas benchmark trading sessions do not align.
- An instrument is newly listed, suspended, delisted, ST-designated, or has too
  few valid bars for a requested window.
- Volume/share units differ among broker SDK builds and cannot be normalized
  confidently.
- A financial report is revised, announced after the requested `as_of`, or has
  duplicate report periods.
- Prior-period revenue/profit is zero or changes sign, making percentage growth
  economically non-comparable.
- Equity or profit is non-positive, making PB, ROE, earnings yield, or
  cash-flow-quality interpretation invalid for a preset.
- A company changes sector or a fund changes benchmark/exposure over history.
- A required factor is available for only part of the universe.
- All candidates fail filters or tie after valid rank factors.
- The result cache expires between screen and explanation.
- The optional database becomes unavailable during snapshot persistence.

## Success Criteria

- **SC-001**: Catalog contract tests cover 100% of declared P0 factors, types,
  domains, windows, profiles, availability states, and localized descriptions.
- **SC-002**: A CSI 500 ETF fixture excludes S&P 500 and unrelated `500`
  lookalikes before ranking and orders valid products by disclosed execution
  factors.
- **SC-003**: No automated test can produce a cross-asset rank or apply the
  ordinary-company fundamental preset to a bank, broker, or insurer.
- **SC-004**: Historical financial fixtures prove that reports announced after
  `as_of` never affect filters, ranks, or explanations.
- **SC-005**: For every returned candidate, displayed contribution totals match
  the declared rank score within documented numeric tolerance.
- **SC-006**: Missing, stale, permissioned, and non-comparable factor fixtures
  produce explicit diagnostics under all supported missing policies.
- **SC-007**: Current screening and explanation work with PostgreSQL disabled;
  database failure does not corrupt or relabel the captured in-memory result.
- **SC-008**: Repeated requests reuse eligible stable/daily cache entries while
  fresh snapshot factors expire according to policy and are never mislabeled.
- **SC-009**: Every screen is bounded, auditable, JSON-clean, and leaves
  existing MCP tool contracts unchanged.
- **SC-010**: Tool-description review verifies that an agent can discover valid
  factors, avoid guessing codes or exposure groups, run a screen, interpret
  partial coverage, and request an explanation without external instructions.

## Out of Scope

- Convertible-bond, option, futures, fund-of-funds, portfolio optimization, or
  cross-asset ranking.
- Dedicated bank, broker, and insurer fundamental models.
- Hundreds of overlapping technical indicators such as exhaustive MACD, KDJ,
  RSI, CCI, and candlestick-pattern variants.
- News, social sentiment, analyst forecasts, alternative data, Level-2 order
  flow, and ungoverned external data enrichment.
- A proprietary opaque AI score, automatic risk-preference inference, return
  guarantee, or personalized investment recommendation.
- Arbitrary QMT formula execution or user-supplied Python expressions.
- Order generation, trade confirmation, scheduling, or any xttrade operation.
- A screener MCP App in the first implementation. Text and structured output
  ship first; an App requires a separate story prototype and feature decision.
- A mandatory historical factor warehouse or backtesting engine. PostgreSQL
  factor snapshots and point-in-time backtests are a follow-up.

## Research Basis

- Official XtData market and financial-data fields, including report and
  announcement time:
  <https://dict.thinktrader.net/nativeApi/xtdata.html>
- Official ETF creation/redemption and IOPV capability boundaries:
  <https://dict.thinktrader.net/dictionary/floorfunds.html>
- Size and value in China, supporting size-quality gates and earnings yield over
  an unconditional small-cap/value assumption:
  <https://hub.hku.hk/handle/10722/273695>
- A-share factor-model evidence for value, ROE/profitability, and conditional
  momentum rather than assuming imported factors transfer unchanged:
  <https://www.sciencedirect.com/science/article/pii/S105752192300491X>
- Amihud's low-input illiquidity measure:
  <https://www.sciencedirect.com/science/article/pii/S1386418101000246>

These sources motivate the initial catalog but do not turn preset thresholds
or factor ranks into investment advice or expected-return guarantees.

## Assumptions

- The appliance remains private, stateful, and read-only for this feature.
- QMT/xtdata coverage and permission differ by broker pack; runtime capability
  reporting is authoritative for availability.
- Stable metadata may be cached aggressively, completed daily data may be
  cached by date/version, and live execution factors require short freshness.
- The implementation will start with text plus structured MCP output. Product
  evidence, not the mere presence of a result table, will decide whether a
  future screener MCP App is warranted.
- Preset thresholds are versioned defaults for research convenience, not hard
  validation domains or personalized recommendations.
