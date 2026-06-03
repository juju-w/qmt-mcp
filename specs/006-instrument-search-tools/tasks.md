# Tasks: Instrument Search & Symbol Resolution Tools

## Implementation

- [x] Add `qmt_mcp_xtdata/search_cache.py` for cache path validation, atomic JSON
  writes, lock handling, stale detection, and seed merge.
- [x] Add `qmt_mcp_xtdata/search_index.py` for normalization, deterministic
  scoring, filtering, and resolve guidance.
- [x] Add pinyin-initial / ASCII-shorthand generation and matching for cached
  names and aliases.
- [x] Add built-in seed data for a small set of common indices/ETFs/aliases.
- [x] Add cached liquidity/size metric refresh for bounded quote-supported
  candidates.
- [x] Register `qmt_xtdata_search_instruments`.
- [x] Register `qmt_xtdata_resolve_instrument`.
- [x] Register `qmt_xtdata_search_sectors`.
- [x] Register `qmt_xtdata_refresh_instrument_cache`.
- [x] Register `qmt_xtdata_instrument_cache_status`.
- [x] Write full agent-facing docstrings/descriptions for every registered tool,
  including use cases, defaults, ranking/cache semantics, next tools, and common
  mistakes.

## Validation

- [x] Validate query length, filters, limit, refresh mode, and sector count.
- [x] Mark external/HK results as quote-supported `unknown` unless verified.
- [x] Validate `rank_by` and verify deterministic ordering for combined,
  relevance, liquidity, size, amount, and volume modes.
- [x] Verify initials search examples such as `ZGWX -> 中国卫星` and
  case-insensitive matching such as `zgpa`.
- [x] Verify ranking/disambiguation for stock-vs-ETF-vs-index and external/HK
  candidates.
- [x] Ensure search uses cache/seed hot path and does not scan xtdata every call.
- [x] Smoke-check MCP tool discovery output to ensure docstrings are present and
  specific enough for an AI client to choose tools correctly.
- [x] Add smoke with fake xtdata sector/detail APIs.
- [x] Run live smoke: refresh cache, search `天岳`, resolve `恒生科技`, then call
  snapshot/bars with the selected candidate.
- [x] Run live smoke: search `纳指` with `rank_by=liquidity` and verify higher
  turnover ETF candidates rank first when metrics are available.

## Documentation

- [x] Update 003 tool catalog after implementation.
- [x] Document MCP prompt guidance: agents should call search/resolve before
  guessing codes.
