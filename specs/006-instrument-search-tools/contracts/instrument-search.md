# Contract: Instrument Search MCP Tools

All tools use 002 authentication, audit, worker, and error-envelope behavior.

## Tool Docstring Standard

Each registered MCP tool description/docstring should be written for an AI agent
that may not know QMT codes. Include:

- Purpose and when to use the tool.
- When not to use the tool.
- Required and optional arguments with defaults and bounds.
- Cache behavior and freshness implications.
- Ranking or confidence semantics.
- How to interpret key output fields.
- Recommended next tool calls.
- Common mistakes to avoid.

Example style for `qmt_xtdata_search_instruments`:

```text
Search cached xtdata instruments by natural-language name, code, alias, sector,
pinyin initials, or theme before calling quote/history tools. Use this when the
user says "天岳", "ZGWX", "恒生科技", "纳指", or any phrase that may not be a valid
QMT code. Do not use this to fetch prices; after selecting a high-confidence
candidate, call qmt_xtdata_snapshot, qmt_xtdata_bars, or
qmt_xtdata_instrument_detail with the returned code. Default ranking is
combined relevance + quote support + type preference + cached liquidity. Set
rank_by=liquidity for ETF/theme searches where the most actively traded proxy is
preferred. If confidence is low or results are ambiguous, ask the user to
clarify instead of inventing a code.
```

## `qmt_xtdata_search_instruments`

Input:

```json
{
  "query": "天岳",
  "sectors": [],
  "markets": [],
  "types": [],
  "include_external": false,
  "limit": 20,
  "refresh": "stale",
  "rank_by": "combined",
  "include_metrics": true
}
```

Rules:

- `query` must be 1-64 chars after trimming.
- `limit` max is 100.
- `refresh=stale` may refresh cache when older than configured TTL.
- `rank_by` allowed values: `combined`, `relevance`, `liquidity`, `size`,
  `amount`, `volume`.
- Chinese pinyin-initial and ASCII shorthand matching is enabled by default.
  Matching is case-insensitive and punctuation-insensitive.
- The hot search path reads cache/seed data. It must not call quote/history for
  every candidate. Liquidity/size ranking uses cached metrics from refresh jobs.
- Ranking ties are broken by cached liquidity values, preferring latest amount,
  rolling amount, then volume metrics.

Output:

```json
{
  "ok": true,
  "query": "天岳",
  "cache": {
    "state": "fresh",
    "updated_at": "2026-06-03T12:00:00+08:00",
    "record_count": 6000,
    "partial": false
  },
  "results": [
    {
      "code": "688234.SH",
      "name": "天岳先进",
      "market": "SH",
      "instrument_type": "stock",
      "sectors": ["沪深A股", "科创板"],
      "score": 92,
      "rank_score": 93.4,
      "match_reason": ["name_substring:天岳"],
      "rank_factors": ["quote_supported:true", "type:stock", "liquidity:available"],
      "quote_supported": "true",
      "liquidity": {
        "latest_amount": 123456789.0,
        "avg_amount_20d": 98765432.0,
        "avg_volume_20d": 1234567,
        "metrics_updated_at": "2026-06-03T12:00:00+08:00",
        "metrics_source": "bars"
      },
      "size": {
        "total_volume": 1000000000,
        "float_volume": 700000000,
        "estimated_market_value": 50000000000.0
      },
      "next_tools": ["qmt_xtdata_snapshot", "qmt_xtdata_bars", "qmt_xtdata_instrument_detail"],
      "warnings": []
    }
  ],
  "truncated": false
}
```

Pinyin-initial example:

```json
{
  "ok": true,
  "query": "ZGWX",
  "results": [
    {
      "code": "600118.SH",
      "name": "中国卫星",
      "market": "SH",
      "instrument_type": "stock",
      "score": 95,
      "rank_score": 94.1,
      "match_reason": ["pinyin_initials_exact:ZGWX"],
      "rank_factors": ["quote_supported:true", "type:stock", "liquidity:available"],
      "quote_supported": "true",
      "next_tools": ["qmt_xtdata_snapshot", "qmt_xtdata_bars", "qmt_xtdata_instrument_detail"],
      "warnings": []
    }
  ],
  "truncated": false
}
```

## `qmt_xtdata_resolve_instrument`

Input:

```json
{
  "query": "恒生科技",
  "prefer_types": ["etf", "index", "stock"],
  "include_external": false,
  "rank_by": "combined",
  "min_score": 70,
  "limit": 5
}
```

Output:

```json
{
  "ok": true,
  "query": "恒生科技",
  "resolved": true,
  "confidence": "high",
  "best": {
    "code": "513130.SH",
    "name": "恒生科技ETF",
    "market": "SH",
    "instrument_type": "etf",
    "score": 91,
    "rank_score": 95.2,
    "match_reason": ["alias_exact:恒生科技", "type_preference:etf"],
    "rank_factors": ["quote_supported:true", "type_preference:etf", "liquidity:high"],
    "quote_supported": "true",
    "liquidity": {
      "avg_amount_20d": 800000000.0,
      "metrics_source": "bars"
    },
    "next_tools": ["qmt_xtdata_snapshot", "qmt_xtdata_bars"]
  },
  "alternates": [],
  "guidance": "Use the best ETF candidate for A-share listed exposure. Ask for clarification before using HK direct stocks.",
  "cache": {
    "state": "fresh",
    "updated_at": "2026-06-03T12:00:00+08:00"
  }
}
```

## `qmt_xtdata_search_sectors`

Input:

```json
{
  "query": "ETF",
  "limit": 50,
  "refresh": "stale"
}
```

Output:

```json
{
  "ok": true,
  "query": "ETF",
  "sectors": [
    {
      "name": "沪深ETF",
      "score": 100,
      "match_reason": ["substring:ETF"]
    }
  ],
  "cache": {
    "state": "fresh",
    "updated_at": "2026-06-03T12:00:00+08:00"
  }
}
```

## `qmt_xtdata_refresh_instrument_cache`

Input:

```json
{
  "sectors": ["沪深A股", "京市A股", "沪深ETF", "沪深指数"],
  "include_external": false,
  "force": false,
  "max_codes": 20000,
  "refresh_metrics": true,
  "metrics_period": "1d",
  "metrics_count": 20
}
```

Rules:

- Calls `download_sector_data()` if available, then sector and detail APIs.
- Must be worker-backed with a longer timeout.
- Must write cache atomically.
- Must return partial success when some sectors fail but others refresh.
- When `refresh_metrics=true`, it may populate bounded rolling liquidity metrics
  for quote-supported candidates using recent bars or snapshots.
- Refresh attempts bar amount/volume first. If bars are unavailable or empty for
  a candidate, refresh may use bounded full-tick snapshot amount/volume as a
  latest-liquidity fallback.

Output:

```json
{
  "ok": true,
  "cache_path": "/broker/cache/instrument-search-v1.json",
  "record_count": 6500,
  "sector_count": 4,
  "partial": false,
  "updated_at": "2026-06-03T12:00:00+08:00",
  "errors": []
}
```

## `qmt_xtdata_instrument_cache_status`

Input:

```json
{}
```

Output:

```json
{
  "ok": true,
  "cache_path": "/broker/cache/instrument-search-v1.json",
  "exists": true,
  "state": "fresh",
  "record_count": 6500,
  "sector_count": 4,
  "updated_at": "2026-06-03T12:00:00+08:00",
  "ttl_seconds": 604800,
  "uses_seed": true
}
```

## Error Guidance

- `not_ready`: xtdata import or QMT connection unavailable and no usable cache.
- `dependency`: xtdata sector/detail function failed unexpectedly.
- `validation`: query/filter/limit invalid.
- `capacity`: refresh/search worker pool exhausted.

When stale cache or seeds are usable, tools should prefer `ok: true` with cache
warnings instead of failing outright.
