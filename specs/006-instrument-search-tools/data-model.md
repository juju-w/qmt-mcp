# Data Model: Instrument Search & Symbol Resolution

## InstrumentSearchCache

| Field | Type | Notes |
|---|---|---|
| `schema_version` | integer | Starts at `1`. |
| `broker_id` | string | From 001/002 resolved config. |
| `created_at` | string | ISO timestamp. |
| `updated_at` | string | ISO timestamp. |
| `source_sectors` | list[string] | Sectors included in the last refresh. |
| `records` | list[InstrumentSearchRecord] | Cached instruments. |
| `sector_names` | list[string] | Cached sector names for sector search. |
| `partial` | bool | True when refresh hit recoverable errors. |
| `errors` | list[object] | Sanitized sector/function errors. |

Default path:

```text
/broker/cache/instrument-search-v1.json
```

## InstrumentSearchRecord

| Field | Type | Notes |
|---|---|---|
| `code` | string | QMT style code, e.g. `510300.SH`, `08133.HK`. |
| `market` | string | Suffix after dot. |
| `name` | string | From `InstrumentName` or seed alias. |
| `aliases` | list[string] | Common names, abbreviations, ETF theme aliases. |
| `pinyin_initials` | list[string] | Best-effort initials for name/aliases, e.g. `ZGWX`. |
| `ascii_aliases` | list[string] | Case-insensitive shorthand aliases, e.g. `HSKJ`, `HS300ETF`. |
| `instrument_type` | string | `stock`, `etf`, `index`, `fund`, `bond`, `future`, `unknown`. |
| `exchange_id` | string | From xtdata detail when available. |
| `instrument_id` | string | From xtdata detail when available. |
| `product_id` | string | From xtdata detail when available. |
| `sectors` | list[string] | Sectors that yielded this code. |
| `quote_supported` | enum | `true`, `false`, `unknown`. |
| `metadata_source` | enum | `xtdata`, `seed`, `merged`. |
| `updated_at` | string | Record refresh time. |
| `raw_fields` | object | Safe detail fields. Bounded. |

## InstrumentSearchRequest

| Field | Type | Notes |
|---|---|---|
| `query` | string | Required, 1-64 chars. Code, name, alias, or theme. |
| `sectors` | list[string] | Optional sector names. Default configured universe. |
| `markets` | list[string] | Optional market filters, e.g. `SH`, `SZ`, `BJ`, `HK`. |
| `types` | list[string] | Optional type filters, e.g. `stock`, `etf`, `index`. |
| `include_external` | bool | Include HK/other non-default markets. Default false. |
| `limit` | integer | Default 20, max 100. |
| `refresh` | enum | `never`, `stale`, `force`. Default `stale`. |
| `rank_by` | enum | `combined`, `relevance`, `liquidity`, `size`, `amount`, `volume`. Default `combined`. |
| `include_metrics` | bool | Include liquidity/size metrics in output. Default true. |

## InstrumentSearchResult

| Field | Type | Notes |
|---|---|---|
| `code` | string | Candidate code. |
| `name` | string | Candidate display name. |
| `market` | string | Market suffix. |
| `instrument_type` | string | Normalized type. |
| `sectors` | list[string] | Matching/source sectors. |
| `score` | number | 0-100. |
| `rank_score` | number | Final sorting score after ranking mode, type priority, quote support, and metrics. |
| `match_reason` | list[string] | Why this result matched. |
| `rank_factors` | list[string] | Why this result was ordered where it was. |
| `quote_supported` | enum | `true`, `false`, `unknown`. |
| `liquidity` | object | Recent amount/volume metrics when available. |
| `size` | object | Share count / market-value estimates when available. |
| `next_tools` | list[string] | Usually `qmt_xtdata_snapshot`, `qmt_xtdata_bars`, `qmt_xtdata_instrument_detail`. |
| `warnings` | list[string] | Low confidence, external market, stale cache, etc. |

## ResolveResult

| Field | Type | Notes |
|---|---|---|
| `resolved` | bool | True when best candidate clears confidence threshold. |
| `best` | InstrumentSearchResult? | Highest-scoring candidate. |
| `alternates` | list[InstrumentSearchResult] | Bounded alternatives. |
| `confidence` | enum | `high`, `medium`, `low`, `ambiguous`. |
| `guidance` | string | Agent-facing next-step instruction. |
| `cache_status` | object | Age, partial/stale flags, source. |

## Scoring Rules

Initial deterministic scoring:

- Exact code match: 100.
- Exact normalized name or alias match: 95.
- Exact pinyin initials or ASCII alias match: 90-95.
- Prefix name/alias match: 85.
- Prefix pinyin initials match: 80-90 depending on length.
- Substring Chinese match: 75.
- Sector/theme alias match: 60-80 depending on type priority.
- ASCII lowercase/punctuation-insensitive match: 50-75.
- External/HK direct instruments are down-ranked unless `include_external=true`.
- ETF proxies are up-ranked for overseas themes when direct quote support is
  unknown or false.
- `rank_by=combined` uses textual relevance first, then quote support, type
  preference, recent average amount, recent volume, and estimated size.
- `rank_by=liquidity` emphasizes rolling amount and volume while retaining a
  minimum relevance floor.
- `rank_by=size` emphasizes estimated market value or fund scale proxies when
  available.

No ML model is required for MVP.

## Pinyin Initials

MVP matching supports initials and ASCII shorthand because many A-share users
type old-school abbreviations:

- `ZGWX` -> `中国卫星`
- `ZGPA` -> `中国平安`
- `HSKJ` -> `恒生科技`
- `HS300ETF` -> `沪深300ETF`

Implementation can be best-effort:

- Generate initials for common CJK characters using a lightweight mapping or an
  optional dependency.
- Store generated initials in cache so search does not recompute them on every
  call.
- Let seed aliases override or supplement generated initials for polyphonic or
  important names.
- Matching is case-insensitive and ignores spaces, hyphens, underscores, and
  punctuation.

## LiquidityMetrics

| Field | Type | Notes |
|---|---|---|
| `latest_amount` | number? | From snapshot or latest bar. |
| `latest_volume` | number? | From snapshot or latest bar. |
| `avg_amount_5d` | number? | Rolling 5 trading-day amount. |
| `avg_amount_20d` | number? | Rolling 20 trading-day amount. |
| `avg_volume_20d` | number? | Rolling 20 trading-day volume. |
| `metrics_updated_at` | string? | ISO timestamp. |
| `metrics_source` | string? | `snapshot`, `bars`, `seed`, `unknown`. |

## SizeMetrics

| Field | Type | Notes |
|---|---|---|
| `total_volume` | number? | From instrument detail when available. |
| `float_volume` | number? | From instrument detail when available. |
| `estimated_market_value` | number? | Latest price * total/float volume when available. |
| `fund_scale` | number? | Optional future ETF/fund scale source if available. |
