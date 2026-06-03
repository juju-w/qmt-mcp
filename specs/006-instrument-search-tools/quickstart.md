# Quickstart: Instrument Search Tools

Goal: let an agent find candidate codes before using market-data tools.

Agent rule of thumb: call `qmt_xtdata_search_instruments` or
`qmt_xtdata_resolve_instrument` before guessing a QMT code from a Chinese name,
ETF theme, shorthand, or pinyin initials. If `resolved=false` or confidence is
ambiguous, inspect alternates or ask the user to clarify before calling
snapshot/bars.

## 1. Confirm streamable HTTP MCP

Connect the MCP client to:

```text
http://<host>:8765/mcp
```

Use the same bearer token as 002/003.

## 2. Check cache status

```text
qmt_xtdata_instrument_cache_status({})
```

Expected:

- If cache exists, `state` is `fresh` or `stale`.
- If cache does not exist, use refresh next.

## 3. Refresh default universe

```text
qmt_xtdata_refresh_instrument_cache({
  "sectors": ["沪深A股", "京市A股", "沪深ETF", "沪深指数"],
  "include_external": false,
  "force": false
})
```

Expected: a bounded record count and atomic JSON cache under `/broker/cache`.

## 4. Search by partial name

```text
qmt_xtdata_search_instruments({
  "query": "天岳",
  "limit": 10
})
```

Expected: candidates with scores and match reasons. The agent should pass the
chosen `code` into `qmt_xtdata_snapshot` or `qmt_xtdata_bars`.

## 5. Resolve a theme

```text
qmt_xtdata_resolve_instrument({
  "query": "恒生科技",
  "prefer_types": ["etf", "index", "stock"],
  "include_external": false,
  "rank_by": "combined"
})
```

Expected: A-share ETF candidates are preferred for overseas themes unless direct
external instruments are explicitly requested.

## 5b. Search by initials

```text
qmt_xtdata_search_instruments({
  "query": "ZGWX",
  "limit": 10
})
```

Expected: `中国卫星` appears as a high-confidence candidate with a
`pinyin_initials_exact` or equivalent match reason.

For liquidity-first ranking:

```text
qmt_xtdata_search_instruments({
  "query": "纳指",
  "types": ["etf"],
  "include_external": false,
  "rank_by": "liquidity",
  "limit": 5
})
```

Expected: Nasdaq-related A-share ETF candidates are ordered by cached recent
turnover/volume after meeting the relevance threshold.

## 6. Search sectors

```text
qmt_xtdata_search_sectors({
  "query": "港股",
  "limit": 20
})
```

Expected: matching sector names. The agent can use a returned sector to rerun
instrument search with a narrower universe.
