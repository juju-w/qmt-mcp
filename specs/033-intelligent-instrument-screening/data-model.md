# Data Model: Intelligent Instrument Screening

## Conventions

- Ratios use decimal JSON numbers: `0.10` means 10 percent.
- Currency values use CNY unless the factor explicitly declares another unit.
- Dates use `YYYYMMDD`; timestamps use RFC 3339 with an explicit offset.
- Instrument codes use the existing QMT `code.market` representation.
- `null` is never a numeric score. A missing factor has a status and reason.
- Factor IDs are stable across additive catalog releases. Formula changes bump
  `factor_version`; incompatible factor semantics require a new factor ID.

## Enumerations

### Asset and profile enums

```text
AssetType       = stock | etf
StockProfile    = auto | non_financial | bank | broker | insurer
EtfProfile      = auto | broad_market_equity | sector_theme_equity
                  | strategy_equity | cross_border_equity
                  | bond | commodity | money_market
UniverseKind    = codes | sector | market | exposure
```

`auto` is a request value, not a resolved profile. A resolved candidate profile
is one concrete profile or `unknown`.

### Factor enums

```text
ValueType       = number | integer | boolean | enum
Unit            = ratio | cny | bps | days | count | score | state
SourceClass     = native | derived | permissioned | external
Freshness       = snapshot | completed_daily | announced_financial
Availability    = available | partial | unavailable | unknown
Observation     = available | missing | stale | not_applicable
MissingReason   = insufficient_history | missing_source_field
                  | unavailable_capability | permission_denied
                  | stale_snapshot | one_sided_quote | suspended
                  | non_comparable_denominator | profile_incompatible
                  | exposure_unresolved | after_as_of
                  | source_error | invalid_source_value
RankDirection   = higher | lower | target | neutral
```

### Request enums

```text
FilterOperator  = eq | ne | gt | gte | lt | lte | between | in | not_in
MissingPolicy   = exclude | neutral | fail
SortDirection   = asc | desc
UniversePolicy  = require_complete | allow_partial
```

`neutral` applies only to optional rank components. It is invalid for a hard
filter.

## FactorDefinition

One immutable catalog definition.

| Field | Type | Rules |
|---|---|---|
| `factor_id` | string | Stable snake-case ID; unique |
| `version` | string | Formula/catalog semantic version |
| `labels` | object | At least `zh-CN` and `en` |
| `description` | object | Agent-facing, localized explanation |
| `asset_types` | array | Non-empty subset of `stock`, `etf` |
| `profiles` | array | Empty means all profiles for the asset |
| `value_type` | enum | Determines validation and operators |
| `unit` | enum | Machine-readable unit |
| `domain` | object | Optional inclusive/exclusive numeric bounds or enum values |
| `operators` | array | Compatible filter operators |
| `rank_direction` | enum | Default ranking interpretation |
| `parameters` | object | Allowed parameter names, types, values, defaults |
| `source_class` | enum | Data-origin class |
| `freshness` | enum | Snapshot, daily, or announced financial |
| `point_in_time` | boolean | Whether historical as-of is supported safely |
| `adjustment` | string/null | Such as `front_ratio` or `none` |
| `nullable` | boolean | Whether valid inputs may still yield missing |
| `required_capabilities` | array | Runtime capabilities needed |
| `formula_summary` | string | Short human-readable formula |
| `presets` | array | Preset IDs that reference the factor |

Runtime fields are layered over the immutable definition:

| Field | Type | Meaning |
|---|---|---|
| `availability` | enum | Active broker/runtime state |
| `availability_reason` | string/null | Why not fully available |
| `coverage_estimate` | ratio/null | Known fraction of requested universe |
| `source_checked_at` | timestamp | Capability/coverage check time |

## FactorRef

A stable factor plus validated parameters.

```json
{
  "factor_id": "return",
  "params": {"window": 60}
}
```

Canonical identity sorts parameter keys and applies catalog defaults. The
canonical example above is `return(window=60)`. An invalid parameter is not
discarded or defaulted.

## UniverseRequest

| Field | Type | Rules |
|---|---|---|
| `kind` | `UniverseKind` | Required |
| `values` | string array | Meaning depends on kind; bounded and deduplicated |
| `name` | string/null | Caller label, never authoritative membership |
| `policy` | `UniversePolicy` | Default `require_complete` |
| `include_suspended` | boolean | Default false for current screens |

Kind-specific semantics:

- `codes`: `values` are exact QMT codes.
- `sector`: `values` are exact official QMT sector names.
- `market`: one value such as `a_share` or `all_etf`.
- `exposure`: one known exposure ID or alias such as `csi_500`/`中证500`.

## ResolvedUniverse

| Field | Type | Meaning |
|---|---|---|
| `asset_type` | enum | Required request type |
| `requested` | `UniverseRequest` | Normalized request |
| `resolved_name` | string | Canonical display name |
| `profile` | string/null | Requested/resolved profile constraint |
| `exposure_group` | string/null | Canonical ETF exposure ID |
| `codes` | string array | Exact deduplicated membership |
| `complete` | boolean | Whether the source claims complete membership |
| `provenance` | array | Sector, cache, reference, alias, or caller membership evidence |
| `resolved_at` | timestamp | Membership capture time |
| `warnings` | string array | Partial/stale/unverified membership warnings |

The service stores the full `codes` internally. Public output may return only a
bounded sample plus count and digest.

## ScreenFilter

| Field | Type | Rules |
|---|---|---|
| `factor` | `FactorRef` | Must support the request asset/profile |
| `operator` | enum | Must be allowed by the factor value type |
| `value` | scalar/array | Type and shape determined by operator |

`between` requires exactly two ordered numeric values. `in` and `not_in`
require a bounded non-empty array. Hard-filter missing behavior comes from the
request and can only be `exclude` or `fail`.

## RankComponent

| Field | Type | Rules |
|---|---|---|
| `factor` | `FactorRef` | Compatible optional rank factor |
| `weight` | number | Finite, greater than zero, at most one |
| `direction` | enum/null | Defaults to catalog direction |
| `target` | number/null | Required only for `target` direction |
| `missing_policy` | enum/null | `exclude`, `neutral`, or `fail`; request default otherwise |

Weights need not sum to one in the request. The normalized values are returned.

## SortComponent

| Field | Type | Rules |
|---|---|---|
| `factor` | `FactorRef` | Compatible sortable factor |
| `direction` | `asc`/`desc` | Required |
| `missing_last` | boolean | Must be true in P0 |

A request provides either `rank` or `sort`, never both. If neither is supplied,
the selected preset must provide one; otherwise validation fails.

## ScreenRequest

| Field | Type | Rules |
|---|---|---|
| `asset_type` | enum | Required |
| `stock_profile` | enum/null | Stock requests only; default `auto` |
| `etf_profile` | enum/null | ETF requests only; default `auto` |
| `universe` | `UniverseRequest` | Required |
| `as_of` | date/null | Latest captured context when absent |
| `preset_id` | string/null | Known versioned preset |
| `filters` | `ScreenFilter[]` | Bounded |
| `rank` | `RankComponent[]` | Mutually exclusive with `sort` |
| `sort` | `SortComponent[]` | Mutually exclusive with `rank` |
| `filter_missing_policy` | enum | `exclude` default; `neutral` invalid |
| `rank_missing_policy` | enum | `exclude` default |
| `limit` | integer | 1 through configured maximum, at most 100 |
| `diagnostics` | enum | `summary` or `detailed` |

Normalization expands the preset first, applies explicit compatible overrides,
fills catalog parameter defaults, canonicalizes codes/aliases, and records both
the original and normalized request.

## DataContext

The immutable capture context shared by all observations in one screen.

| Field | Type | Meaning |
|---|---|---|
| `captured_at` | timestamp | Screen execution capture time |
| `as_of` | date | Effective market/financial cutoff |
| `market_session` | date/null | Latest completed market session |
| `price_adjustment` | string | `front_ratio` for historical return factors |
| `factor_version` | string | Catalog/formula version |
| `broker_id` | string | Internal cache namespace; not necessarily public |
| `sources` | array | Source name, requested range, response time, coverage, warnings |

Live spread/IOPV factors also include their own quote time and age because they
cannot be represented by the daily `as_of` alone.

## FactorObservation

| Field | Type | Meaning |
|---|---|---|
| `code` | string | Instrument identity |
| `factor` | `FactorRef` | Canonical factor identity |
| `status` | `Observation` | Available/missing/stale/not applicable |
| `value` | scalar/null | Typed raw value when available |
| `unit` | enum | Copied from definition |
| `data_as_of` | date/timestamp/null | Effective source cutoff |
| `source` | string | Normalized source name |
| `adjustment` | string/null | Price adjustment where relevant |
| `announcement_time` | timestamp/null | Financial source announcement cutoff |
| `missing_reason` | enum/null | Required when status is not available |
| `details` | object | Bounded formula/source diagnostics |

An observation is immutable once attached to a captured result.

## CandidateRecord

Internal per-instrument state during evaluation.

| Field | Type | Meaning |
|---|---|---|
| `code`, `name`, `market` | strings | Instrument identity |
| `asset_type` | enum | Stock or ETF |
| `profile` | string | Resolved concrete profile or unknown |
| `exposure_group` | string/null | ETF comparable group |
| `membership` | array | Why it belongs to the universe |
| `observations` | map | Canonical FactorRef to FactorObservation |
| `filter_decisions` | array | Ordered pass/fail/missing decisions |
| `eligible` | boolean | Survived hard filters |
| `rejection_reason` | string/null | First deterministic rejection |
| `rank_contributions` | array | Present after ranking |
| `coverage` | ratio | Available optional rank weight / requested weight |
| `score` | number/null | `[0,100]` after ranking |
| `warnings` | array | Candidate-specific caveats |

## FilterDecision

```json
{
  "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
  "operator": "gte",
  "expected": 50000000,
  "actual": 2771000000,
  "outcome": "pass",
  "missing_reason": null
}
```

`outcome` is `pass`, `fail`, or `missing`. Filter order is request order after
preset expansion; the first rejection is deterministic.

## RankContribution

| Field | Type | Meaning |
|---|---|---|
| `factor` | `FactorRef` | Canonical factor identity |
| `raw_value` | scalar/null | Original observation |
| `winsorized_value` | number/null | Value used only for rank transform |
| `percentile` | number/null | `[0,1]`, direction already applied |
| `requested_weight` | number | Caller/preset weight |
| `effective_weight` | number | Weight after normalization/missing policy |
| `contribution` | number | `percentile * effective_weight * 100` |
| `missing_policy` | enum | Applied policy |
| `missing_reason` | enum/null | Reason when unavailable |

Candidate score is the sum of contributions and remains `[0,100]` within
numeric tolerance.

## ScreenResult

| Field | Type | Meaning |
|---|---|---|
| `screen_id` | opaque string | Random, non-sequential result identifier |
| `created_at`, `expires_at` | timestamps | Result-cache lifecycle |
| `request` | object | Original request |
| `normalized_request` | `ScreenRequest` | Exact executed request |
| `data_context` | `DataContext` | Immutable captured context |
| `universe` | `ResolvedUniverse` summary | Membership and provenance |
| `stage_counts` | object | Resolved, eligible, passed, ranked, returned counts |
| `coverage` | object | Per-factor and aggregate coverage |
| `rank_method` | object/null | Transform, weights, winsorization, tie breakers |
| `results` | array | Bounded selected CandidateRecord projection |
| `rejected_summary` | object | Counts grouped by reason; no unbounded row dump |
| `warnings` | array | Screen-level caveats |
| `next_tools` | array | Explanation, download, quote, or bars guidance |

The internal cached result retains bounded details for all evaluated candidates
needed by explanation. Public output returns at most the requested result limit.

## CandidateExplanation

| Field | Type | Meaning |
|---|---|---|
| `screen_id` | string | Parent captured result |
| `code`, `name` | strings | Candidate |
| `selected` | boolean | Whether present in public result rows |
| `eligible` | boolean | Whether all hard filters passed |
| `rank`, `score` | number/null | Final selection values |
| `summary` | string | Concise localized explanation |
| `filter_decisions` | array | Full bounded filter trace |
| `rank_contributions` | array | Full factor contributions |
| `coverage` | ratio | Optional rank coverage |
| `data_context` | object | Dates, adjustment, factor version |
| `warnings` | array | Missing/stale/profile/exposure caveats |

## Cache Keys and Retention

### Factor observation cache key

```text
(broker_id, factor_version, code, as_of_session, adjustment,
 factor_id, canonical_params)
```

Completed-daily and announced-financial entries may live through the configured
TTL for the same source date. Snapshot entries include quote identity and use a
short freshness limit. Missing source errors use a shorter negative-cache TTL.

### Screen result store

- Key: random `screen_id`.
- Default TTL: 15 minutes.
- Default maximum: 100 captured results.
- Payload representation: immutable compact UTF-8 JSON bytes.
- Default payload-size budget: 64 MiB across captured results.
- Eviction: expired first, then least recently accessed when either the count or
  size budget would be exceeded.
- Contents: normalized request, data context, stage diagnostics, and bounded
  candidate explanations.
- Persistence: none in 033.

## State Transitions

```text
received
  -> validated
  -> universe_resolved
  -> data_captured
  -> filtered
  -> ranked_or_sorted
  -> cached
  -> returned
  -> expired
```

Terminal error transitions may occur from validation, universe resolution,
required capability, capacity, source readiness, timeout, or cancellation.
Partial candidate source errors remain inside a successful result only when the
request's missing policy permits them.
