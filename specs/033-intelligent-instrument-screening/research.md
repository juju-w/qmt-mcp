# Research: Intelligent Instrument Screening

## Decision 1: Add a dedicated screening domain package

**Decision**: Implement the feature in a new dependency-light
`qmt_mcp_screening` package. Register its three tools with MCP family `xtdata`
so existing market profiles and `qmt:market` OAuth scope continue to apply.

**Rationale**: Screening has its own catalog, universe, factor, rank, cache, and
explanation concepts. Putting them into the already large
`qmt_mcp_xtdata/tools.py` would couple pure factor logic to MCP registration and
make host-unit testing harder. The data remains xtdata market data, so adding a
new authorization family would create needless profile and scope churn.

**Alternative rejected**: Extend the formula runtime. Feature 018 is
permissioned, allowlisted execution of formulas installed in QMT/投研端. A
portable screener must work on ordinary xtdata installations, cannot execute
caller expressions, and needs server-owned point-in-time semantics.

## Decision 2: Keep the factor catalog in versioned code

**Decision**: Define factors and presets as immutable Python records with stable
IDs and one `FACTOR_VERSION`. Use a registry from factor definition to a pure
calculator. Return runtime availability separately from the static definition.

**Rationale**: A code-owned catalog makes formulas, units, bounds, windows,
missing rules, and descriptions reviewable and reproducible. It also gives the
MCP agent valid alternatives when it invents a factor or unsupported window.

**Alternative rejected**: Load arbitrary JSON formulas or Python expressions.
That weakens validation, creates an execution surface, and cannot reliably
express financial announcement-time rules.

## Decision 3: Do not add NumPy or pandas as screening dependencies

**Decision**: Normalize xtdata outputs at the adapter boundary and calculate
rolling returns, means, volatility, drawdown, percentiles, and financial ratios
with bounded standard-library functions. Proprietary SDK objects and dataframes
never enter the factor/ranking layer.

**Rationale**: Broker packages commonly include NumPy/pandas, but their version
and ABI cannot be treated as a QMT-MCP distribution contract. The selected
windows and bounded universe are simple enough for streaming/list-based Python
calculations. This preserves plain-host unit tests and the lean Windows runtime
policy.

**Alternative rejected**: Depend directly on the broker's NumPy/pandas copy.
That risks ABI shadowing and makes the launcher package behavior broker-specific.

## Decision 4: Resolve universes before computing factors

**Decision**: Build `UniverseResolver` above the 006 instrument cache and exact
xtdata sector membership calls. Support four bounded universe kinds:
`codes`, `sector`, `market`, and `exposure`. Every result records membership
provenance and completeness.

For stocks, `market` resolves from official A-share/Beijing sector lists. For
financial profiles, versioned exact sector aliases resolve bank, broker, and
insurer sets; `non_financial` is a safe residual only when all configured
financial classifier sets loaded successfully.

For ETFs, an `exposure` universe first uses official reference/sector metadata
when available, then a small versioned strict exposure alias catalog. Strict
name-derived membership requires the complete normalized exposure token, not a
code substring such as `500`. Unknown exposure queries return valid known
groups or require explicit codes; they do not fall back to fuzzy rank.

**Rationale**: Search relevance answers "what might the user mean?" Screening
answers "which members are economically comparable?" Keeping these stages
separate fixes the CSI 500 versus S&P 500/code-500 failure mode.

**Alternative rejected**: Feed the top fuzzy-search results directly to the
ranker. Text relevance and factor quality are different dimensions and broad
recall necessarily includes lookalikes.

## Decision 5: Use staged, batched factor evaluation

**Decision**: Evaluate one captured screen in these stages:

1. Resolve and classify at most 5,000 instruments.
2. Apply metadata/data-quality gates.
3. Read daily bars in batches of at most 50 codes and retain only normalized
   series/factor observations, not all raw SDK objects.
4. Apply market-factor hard filters.
5. Read point-in-time financial tables in batches of at most 200 surviving
   stock codes when required.
6. Read current snapshots only for surviving/finalist codes when a fresh spread
   factor is requested.
7. Rank, retain bounded explanation records, and serialize at most 100 rows.

The exact maxima are validated configuration values and are returned in
capacity errors. Smaller explicit universes remain the recommended interactive
path.

**Rationale**: Full A-share history can exceed one million daily observations.
Batching bounds proprietary SDK calls and memory; staging prevents expensive
financial and snapshot calls for candidates already rejected by cheap gates.

**Alternative rejected**: Materialize a dataframe for the complete universe.
It creates large transient memory use and ties the implementation to dataframe
shape/version behavior.

## Decision 6: Make the screen tool MCP Task-capable

**Decision**: Add `qmt_screen_instruments` to the default MCP Task tool set.
`qmt_factor_catalog` and `qmt_explain_screen_result` stay synchronous. A client
without Tasks can still screen a bounded narrow universe through the normal
tool path.

**Rationale**: Full-market history and financial reads may exceed an ordinary
interactive request while factor discovery and explanation should be quick.
The repository already provides durable 2026-07-28 Task lifecycle,
notifications, cancellation, and owner/scope enforcement.

**Alternative rejected**: Add a second job queue or background worker API. It
would duplicate the stable MCP Tasks implementation.

## Decision 7: Use announcement-time financial timelines

**Decision**: Request official financial tables with
`report_type=announce_time`. Normalize report period and announcement time,
discard observations announced after `as_of`, and select the latest announced
version per report period.

Income and cash-flow TTM values use cumulative-statement arithmetic:

```text
TTM = current YTD + prior fiscal year - prior-year comparable YTD
```

If the latest available period is a fiscal year, that annual value is the TTM.
Balance-sheet factors use the latest report announced by `as_of`. Growth across
zero, ratios with non-positive required denominators, missing comparison
periods, and irreconcilable duplicate rows return a typed missing reason.

**Rationale**: Filtering by report period alone leaks future disclosures into
historical screens. The official API exposes both report- and announcement-time
views and the required Balance, Income, CashFlow, Capital, and Pershareindex
tables.

**Source**: <https://dict.thinktrader.net/nativeApi/xtdata.html>

**Alternative rejected**: Use the newest local row regardless of announcement
date. That is acceptable for a current quote table but invalid for historical
factor tests.

## Decision 8: Keep price conventions explicit

**Decision**: Use `front_ratio` adjusted completed daily closes for return,
moving average, volatility, drawdown, and relative-strength factors. Use the
unadjusted as-of close plus the latest shares announced by that time for market
capitalization. Use live unadjusted bid/ask for spread.

**Rationale**: Corporate actions should not appear as economic returns, while
market capitalization and execution prices must remain in actual currency
units. Every observation returns its adjustment and source date.

**Alternative rejected**: Use one price series for every factor. That either
introduces false return jumps or creates fictitious adjusted market values.

## Decision 9: Use explainable within-universe percentile ranking

**Decision**: Apply hard filters first. Transform each rank factor to a
comparable-universe percentile with its catalog direction, winsorizing only the
cross-sectional transform at fixed disclosed 1st/99th percentiles when the
universe has enough observations. Normalize positive weights to one and return
raw value, percentile, effective weight, and contribution. Tie breakers are
coverage, the first declared rank factor, average amount, then code.

**Rationale**: Currency, ratios, volatility, and market value cannot be summed
in raw units. Percentiles are bounded, explainable, and less sensitive to
extreme accounting values than raw z-scores.

**Alternative rejected**: A server-wide AI score or global z-score. It hides
meaning, changes with unrelated assets, and invites cross-asset misuse.

## Decision 10: Never silently impute required factors

**Decision**: Hard filters always exclude or fail on missing data. Neutral
imputation is allowed only for an optional rank component when explicitly
selected; it uses percentile 0.5, renormalizes effective weights, records the
missing reason, and reduces candidate coverage/confidence.

**Rationale**: Zero is a meaningful value for returns and many fundamentals. It
cannot safely represent missing, stale, unavailable, permission-denied, or
non-comparable data.

## Decision 11: Keep current caches in memory and defer a factor warehouse

**Decision**: Reuse the 006 JSON cache for stable instrument metadata and the
012 bars warehouse only through existing reads where efficient. Add two bounded
in-memory stores:

- A factor-observation cache keyed by broker, factor version, code, as-of
  session, adjustment, factor ID, and parameters.
- A random-ID screen-result store that retains immutable compact JSON bytes for
  exact explanations, with a default 15-minute TTL, 100-result maximum, and
  64 MiB payload budget.

Do not add a PostgreSQL migration in 033. A later feature can persist
point-in-time factor snapshots after formulas and contracts stabilize.

**Rationale**: Current screening must work on a simple Windows installation.
Long-term factor retention has separate schema, correction, retention, and
backfill concerns that should not be smuggled into the first screener.

**Alternative rejected**: Require PostgreSQL. It conflicts with the private
desktop deployment goal and offers little value before historical snapshots are
part of the product contract.

## Decision 12: Do not auto-download data from a read-only screen

**Decision**: Screening reads locally available xtdata history/reference data.
When required financial or ETF reference coverage is missing, return guidance
to call the existing explicit download tools and rerun. Do not call download
APIs inside `qmt_screen_instruments`.

**Rationale**: Download APIs mutate terminal-side caches, may be long-running,
and are already classified as manage-scope operations. A read-only market tool
must not hide such side effects.

## Decision 13: Ship text and structured output before an MCP App

**Decision**: Use concise text renderers plus complete `structuredContent` for
all three tools. Do not bind a UI resource in 033. Do not add dedicated qmtctl
commands in the first implementation; generic MCP clients can call the tools.

**Rationale**: The unresolved product risk is screening correctness, not table
rendering. Once real usage proves which filters, comparisons, and confirmation
interactions matter, a separate single-HTML story prototype can justify an App.

**Alternative rejected**: Build the screener UI alongside the factor engine.
It doubles scope before the data and ranking contract has been validated.

## Evidence for the Initial Factor Scope

- Official XtData market, instrument, sector, and point-in-time financial API:
  <https://dict.thinktrader.net/nativeApi/xtdata.html>
- Official ETF creation/redemption and IOPV boundaries:
  <https://dict.thinktrader.net/dictionary/floorfunds.html>
- China-specific size/value evidence, including shell-value distortion in the
  smallest stocks and stronger earnings-yield semantics:
  <https://hub.hku.hk/handle/10722/273695>
- A-share evidence for value, ROE/profitability, and conditional momentum:
  <https://www.sciencedirect.com/science/article/pii/S105752192300491X>
- Low-input Amihud illiquidity definition:
  <https://www.sciencedirect.com/science/article/pii/S1386418101000246>

The evidence guides catalog selection. It does not establish a return guarantee
or turn a preset into personalized investment advice.
