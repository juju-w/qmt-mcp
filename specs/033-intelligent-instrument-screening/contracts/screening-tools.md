# Contract: Intelligent Screening MCP Tools

All tools use the existing result envelope, structured output, audit wrapper,
market profile, and OAuth scopes. They are read-only and registered under
family `xtdata`.

Successful MCP calls contain a concise text rendering and the same complete
object in `structuredContent`. Examples below show `structuredContent` only.

## Tool: `qmt_factor_catalog`

### Purpose

Discover valid screening factors, parameters, ranges, presets, profiles, and
runtime capability before constructing a screen. Agents SHOULD call this tool
when they do not already have a catalog version compatible with the server.

Agents MUST NOT invent a factor ID, window, profile, or ETF exposure group. The
catalog is not a market screen and does not return candidate instruments.

### Input

```json
{
  "asset_type": "etf",
  "stock_profile": "",
  "etf_profile": "broad_market_equity",
  "include_unavailable": true,
  "locale": "zh-CN"
}
```

| Field | Required | Contract |
|---|---|---|
| `asset_type` | yes | `stock` or `etf` |
| `stock_profile` | no | Empty or a catalog stock profile; invalid for ETF |
| `etf_profile` | no | Empty or a catalog ETF profile; invalid for stock |
| `include_unavailable` | no | Default true; false hides only runtime-unavailable factors, not P0 definitions |
| `locale` | no | `zh-CN` or `en`; default `zh-CN` |

### Successful output

```json
{
  "ok": true,
  "catalog_version": "screening-factors-v1",
  "generated_at": "2026-08-16T10:00:00+08:00",
  "asset_type": "etf",
  "profile": "broad_market_equity",
  "profiles": [
    {"id": "broad_market_equity", "label": "宽基股票ETF"}
  ],
  "factors": [
    {
      "factor_id": "avg_amount",
      "label": "平均成交额",
      "description": "已完成交易日的日成交额均值，用于容量和流动性筛选。",
      "asset_types": ["stock", "etf"],
      "profiles": [],
      "value_type": "number",
      "unit": "cny",
      "domain": {"minimum": 0},
      "operators": ["gt", "gte", "lt", "lte", "between"],
      "rank_direction": "higher",
      "parameters": {
        "window": {"type": "integer", "allowed": [20, 60], "default": 20}
      },
      "source_class": "derived",
      "freshness": "completed_daily",
      "point_in_time": true,
      "adjustment": "none",
      "nullable": true,
      "availability": "available",
      "availability_reason": null,
      "required_capabilities": ["daily_bars"],
      "formula_summary": "mean(amount) over completed sessions",
      "presets": ["etf_research", "etf_trade_friendly"]
    },
    {
      "factor_id": "premium_to_iopv",
      "label": "IOPV溢折价率",
      "value_type": "number",
      "unit": "ratio",
      "availability": "unavailable",
      "availability_reason": "installed xtdata runtime does not expose fresh ETF IOPV",
      "required_capabilities": ["etf_iopv"]
    }
  ],
  "presets": [
    {
      "preset_id": "etf_trade_friendly",
      "version": 1,
      "intent": "同一跟踪暴露内优先选择成交活跃、上市时间充分的ETF",
      "expanded_request_fragment": {}
    }
  ],
  "known_exposure_groups": [
    {"id": "csi_500", "label": "中证500", "aliases": ["中证500", "CSI500"]}
  ],
  "limits": {
    "max_universe_codes": 5000,
    "max_factor_refs": 24,
    "max_results": 100
  },
  "next_tools": ["qmt_screen_instruments"]
}
```

The full output returns all required `FactorDefinition` fields from
`data-model.md`; the second factor above is abbreviated only for readability.

### Draft agent-facing description

> Discover the server-owned screening catalog for one asset type before calling
> `qmt_screen_instruments`. Returns valid stock/ETF profiles, factor IDs,
> parameters/windows, value types and decimal units, filter operators, default
> rank direction, presets, runtime availability, freshness, point-in-time
> support, capability requirements, known ETF exposure groups, and limits. Use
> this when translating natural-language conditions or after an invalid-factor
> error. Do not guess factor IDs or use stock fundamentals for ETFs/financial
> companies. This tool lists capabilities; it does not screen instruments.

## Tool: `qmt_screen_instruments`

### Purpose

Resolve one comparable stock or ETF universe, apply typed hard filters, and
sort or rank the survivors with explainable factor contributions. This tool is
Task-capable for large universes.

Search tools discover possible codes or phrases; this tool establishes strict
membership and factor rank. An agent SHOULD resolve an ambiguous instrument or
ETF exposure first and MUST NOT pass fuzzy search score as a screening factor.

### Input

```json
{
  "asset_type": "etf",
  "stock_profile": "",
  "etf_profile": "broad_market_equity",
  "universe": {
    "kind": "exposure",
    "values": ["csi_500"],
    "policy": "require_complete",
    "include_suspended": false
  },
  "as_of": "",
  "preset_id": "etf_trade_friendly",
  "filters": [],
  "rank": [],
  "sort": [],
  "filter_missing_policy": "exclude",
  "rank_missing_policy": "exclude",
  "limit": 5,
  "diagnostics": "summary"
}
```

### Input object contracts

`universe`:

```json
{
  "kind": "codes | sector | market | exposure",
  "values": ["non-empty bounded strings"],
  "name": "optional display label",
  "policy": "require_complete | allow_partial",
  "include_suspended": false
}
```

`filters[]`:

```json
{
  "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
  "operator": "gte",
  "value": 50000000
}
```

`rank[]`:

```json
{
  "factor": {"factor_id": "return", "params": {"window": 60}},
  "weight": 0.4,
  "direction": "higher",
  "target": null,
  "missing_policy": "exclude"
}
```

`sort[]`:

```json
{
  "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
  "direction": "desc",
  "missing_last": true
}
```

### Validation rules

- `asset_type` is required and determines the valid profile and factors.
- Exactly one `universe` is required. `values` are interpreted by `kind` and
  never fuzzy-matched silently.
- `as_of` is empty or `YYYYMMDD`. Empty captures the latest available daily,
  financial, and requested live sources and reports each timestamp separately.
- `preset_id` is optional. Preset expansion is returned in
  `normalized_request`.
- At most the configured number of filters plus rank/sort factor references is
  accepted.
- A request contains `rank` or `sort`, not both. A preset may supply one when
  both arrays are empty.
- `neutral` is rejected for `filter_missing_policy`.
- `limit` is between 1 and 100 and cannot exceed the configured maximum.
- Fundamental factors require stock profile `non_financial`; auto resolution
  must establish that profile before evaluation.
- ETF ranking that claims one exposure requires a resolved `exposure_group`.
- Snapshot-only factors are unavailable for historical `as_of` unless an exact
  source snapshot exists; the server never substitutes today's spread.

### Successful output

The values below are illustrative fixture data, not a market recommendation.

```json
{
  "ok": true,
  "screen_id": "scr_8c989e5c3b7840dbb91ce4f9ab2dad91",
  "created_at": "2026-08-16T10:00:00+08:00",
  "expires_at": "2026-08-16T10:15:00+08:00",
  "request": {},
  "normalized_request": {
    "asset_type": "etf",
    "etf_profile": "broad_market_equity",
    "universe": {"kind": "exposure", "values": ["csi_500"]},
    "preset_id": "etf_trade_friendly",
    "filters": [
      {
        "factor": {"factor_id": "listing_days", "params": {}},
        "operator": "gte",
        "value": 250
      },
      {
        "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
        "operator": "gte",
        "value": 100000000
      }
    ]
  },
  "data_context": {
    "captured_at": "2026-08-16T10:00:00+08:00",
    "as_of": "20260816",
    "market_session": "20260814",
    "price_adjustment": "front_ratio",
    "factor_version": "screening-factors-v1",
    "sources": [
      {"name": "instrument-cache", "state": "fresh", "as_of": "2026-08-16T09:00:00+08:00"},
      {"name": "xtdata-daily-bars", "as_of": "20260814"},
      {"name": "xtdata-snapshot", "as_of": "2026-08-16T10:00:00+08:00"}
    ]
  },
  "universe": {
    "resolved_name": "中证500 ETF",
    "exposure_group": "csi_500",
    "complete": true,
    "member_count": 5,
    "membership_digest": "sha256:...",
    "provenance": ["strict-exposure-alias:csi_500"],
    "warnings": []
  },
  "stage_counts": {
    "resolved": 5,
    "data_eligible": 5,
    "passed_filters": 4,
    "ranked": 4,
    "returned": 4
  },
  "coverage": {
    "overall": 1.0,
    "by_factor": {
      "avg_amount(window=20)": 1.0,
      "bid_ask_spread_bps": 1.0
    }
  },
  "rank_method": {
    "type": "weighted_percentile",
    "winsorization": [0.01, 0.99],
    "tie_breakers": ["coverage", "first_rank_factor", "avg_amount", "code"]
  },
  "results": [
    {
      "rank": 1,
      "code": "510500.SH",
      "name": "中证500ETF南方",
      "asset_type": "etf",
      "profile": "broad_market_equity",
      "exposure_group": "csi_500",
      "score": 94.2,
      "coverage": 1.0,
      "key_factors": [
        {
          "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
          "status": "available",
          "value": 2771000000,
          "unit": "cny",
          "percentile": 1.0,
          "effective_weight": 0.6,
          "contribution": 60.0,
          "data_as_of": "20260814"
        }
      ],
      "warnings": []
    }
  ],
  "rejected_summary": {
    "total": 1,
    "by_reason": {"filter:avg_amount(window=20)": 1}
  },
  "warnings": [],
  "next_tools": [
    "qmt_explain_screen_result",
    "qmt_xtdata_snapshot",
    "qmt_xtdata_kline_chart"
  ]
}
```

### Text rendering

The text content includes:

- Captured asset/profile/universe and source dates.
- Resolved, passed, and returned counts.
- At most ten ranked `code name score` rows with two key factor values.
- Coverage, stale/partial/unresolved warnings.
- Guidance to call `qmt_explain_screen_result` with the `screen_id` and exact
  code for details.

It does not dump every factor observation or rejected candidate into model
context.

### Draft agent-facing description

> Screen one strict, comparable A-share stock or ETF universe with server-owned
> factors. Call `qmt_factor_catalog` first if factor IDs, windows, profiles,
> decimal units, presets, or exposure groups are uncertain. Search/resolve tools
> may discover candidates, but fuzzy relevance is never a rank factor. Provide
> required `asset_type`, one exact universe (`codes`, official `sector`,
> `market`, or known ETF `exposure`), typed hard filters, and either rank or sort
> rules; a preset may expand them. Stocks and ETFs never cross-rank, ordinary
> fundamentals never apply to banks/brokers/insurers, and "best ETF" ranking
> requires one resolved exposure group. Financial factors use announcement-time
> data; snapshot spread/IOPV require fresh quotes. Missing data is never zero.
> Large universes can run as MCP Tasks. Returns a captured `screen_id`, source
> dates, stage counts, coverage, explainable rows, and warnings. Use
> `qmt_explain_screen_result` for one candidate; use explicit download tools and
> rerun when required local history/reference data is missing.

## Tool: `qmt_explain_screen_result`

### Purpose

Explain one selected or rejected candidate from the exact captured screen. It
does not fetch new quotes, recompute factors, or change the rank.

### Input

```json
{
  "screen_id": "scr_8c989e5c3b7840dbb91ce4f9ab2dad91",
  "code": "510500.SH",
  "locale": "zh-CN"
}
```

| Field | Required | Contract |
|---|---|---|
| `screen_id` | yes | Opaque ID returned by a non-expired screen |
| `code` | yes | Exact candidate code from the resolved universe |
| `locale` | no | `zh-CN` or `en`; default `zh-CN` |

### Successful output

```json
{
  "ok": true,
  "screen_id": "scr_8c989e5c3b7840dbb91ce4f9ab2dad91",
  "code": "510500.SH",
  "name": "中证500ETF南方",
  "selected": true,
  "eligible": true,
  "rank": 1,
  "score": 94.2,
  "coverage": 1.0,
  "summary": "该标的通过全部流动性和上市时间条件，并在同一中证500 ETF组内具有较高成交额和较窄有效价差。",
  "filter_decisions": [
    {
      "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
      "operator": "gte",
      "expected": 100000000,
      "actual": 2771000000,
      "outcome": "pass",
      "missing_reason": null
    }
  ],
  "rank_contributions": [
    {
      "factor": {"factor_id": "avg_amount", "params": {"window": 20}},
      "raw_value": 2771000000,
      "winsorized_value": 2771000000,
      "percentile": 1.0,
      "requested_weight": 0.6,
      "effective_weight": 0.6,
      "contribution": 60.0,
      "missing_policy": "exclude",
      "missing_reason": null
    }
  ],
  "data_context": {
    "as_of": "20260816",
    "market_session": "20260814",
    "factor_version": "screening-factors-v1"
  },
  "warnings": [],
  "next_tools": ["qmt_xtdata_snapshot", "qmt_xtdata_kline_chart"]
}
```

### Expired or unknown result

```json
{
  "ok": false,
  "error_type": "not_found",
  "error": "screen result is missing or expired",
  "details": {
    "screen_id": "scr_...",
    "guidance": "Rerun qmt_screen_instruments; do not treat a new screen as the same captured result."
  }
}
```

### Draft agent-facing description

> Explain why one exact instrument passed, failed, or ranked where it did in a
> previously captured `qmt_screen_instruments` result. Requires the returned
> `screen_id` and a code from that resolved universe. Returns hard-filter
> decisions, raw factor values, percentiles, weights, score contributions,
> coverage, source dates, missing reasons, and warnings without fetching new
> data. Use this before presenting a screening conclusion or comparing close
> candidates. If the result expired, rerun the original screen and disclose the
> new data context; never claim a newly computed explanation belongs to the old
> screen.

## Error Contract

All errors use the existing envelope. Screening-specific examples include:

| `error_type` | Example condition | Required details |
|---|---|---|
| `validation` | Unknown factor/window/operator/profile | Invalid value plus valid alternatives |
| `validation` | Rank and sort both supplied | Conflicting fields |
| `not_ready` | QMT not logged in or history absent | Missing source and next/download tool |
| `capability` | Required IOPV/financial capability absent | Required capability and available alternatives |
| `dependency` | xtdata source call failed | Stage and bounded source error |
| `capacity` | Universe/factor/output limit exceeded | Requested value and configured maximum |
| `timeout` | Synchronous client exceeds bounded execution | Narrow-universe or Task guidance |
| `not_found` | Unknown/expired `screen_id` or code outside result | Rerun/valid-code guidance |
| `cancelled` | MCP Task cancellation | Last completed stage when available |

Candidate-level missing source data is not automatically a tool error. It is
handled according to the validated missing policy and surfaced in coverage.

## Tool Behavior and Access

| Tool | Family | Read-only | Task-capable | Required OAuth scopes |
|---|---|---|---|---|
| `qmt_factor_catalog` | `xtdata` | yes | no | `qmt:read qmt:market` |
| `qmt_screen_instruments` | `xtdata` | yes | yes | `qmt:read qmt:market` |
| `qmt_explain_screen_result` | `xtdata` | yes | no | `qmt:read qmt:market` |

The tools are visible in `full`, `readonly`, and `market` profiles, hidden in
`account` and `core`, and governed by the existing custom allow/deny policy.
