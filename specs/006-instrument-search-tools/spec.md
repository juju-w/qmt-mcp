# Feature Specification: Instrument Search & Symbol Resolution Tools

**Status**: Implemented and live-smoke verified
**Depends on**: 002 (MCP core), 003 (xtdata market-data tools)

## Summary

Add an xtdata-backed instrument discovery layer so agents can find tradable or
observable symbols from natural-language names, partial names, aliases, sector
names, or uncertain user input. This feature reduces hallucinated codes by
making "search first, quote second" the default workflow.

The core idea is to build a local, refreshable instrument cache from official
xtdata primitives:

- `xtdata.download_sector_data()` when available
- `xtdata.get_sector_list()`
- `xtdata.get_stock_list_in_sector(sector)`
- `xtdata.get_instrument_detail(code, False)`

The cache is persisted under the broker pack data area and supplemented by a
small built-in seed/alias list for common indices and ETFs. The seed list is a
bootstrap hint, not an authority; xtdata remains the source of truth once ready.

## Why This Matters

Current tools assume the agent already knows `510300.SH` or `688234.SH`.
Less-capable or hallucination-prone agents often know only "沪深300 ETF",
"天岳", "恒生科技", "腾讯", or "纳指". Without a search/resolve tool they either
guess codes or fail before using the useful market-data tools.

This feature gives agents a bounded, auditable way to ask:

1. "What code likely matches this phrase?"
2. "Is this direct stock/ETF/index data, or only an A-share ETF proxy?"
3. "Which candidates are safe to pass into snapshot/bars/detail?"

## User Scenarios

### US1 - Agent searches by partial Chinese name (P1)

**Acceptance**:
1. Given the query `天岳`, when the agent calls `qmt_xtdata_search_instruments`, then the response includes matching instruments such as candidates whose instrument name contains `天岳`.
2. Each candidate includes `code`, `name`, `market`, `instrument_type`, `sectors`, `score`, `match_reason`, and `quote_supported`.
3. Results are bounded and sorted by the requested ranking mode. The default
   ranking prioritizes textual relevance, quote support, type preference, and
   recent liquidity.

### US1b - Agent searches by pinyin initials or shorthand (P1)

**Acceptance**:
1. Given the query `ZGWX`, when the agent calls
   `qmt_xtdata_search_instruments`, then the response can include `中国卫星`.
2. Given mixed shorthand such as `zgpa`, `HSKJ`, or `hs300etf`, matching is
   case-insensitive and punctuation-insensitive.
3. Results include a match reason such as `pinyin_initials_exact:ZGWX` or
   `alias_ascii:HSKJ` so the agent can explain why a shorthand matched.

### US2 - Agent resolves ambiguous ETF/index themes (P1)

**Acceptance**:
1. Given `恒生科技` or `纳指`, the search tool returns A-share listed ETF/index
   candidates when available, rather than inventing foreign stock codes.
2. If HK or overseas direct instruments appear from xtdata sector metadata, the
   response marks them as `quote_supported: unknown|false` unless the current
   code validator/runtime can actually quote them.
3. The response includes a `guidance` field telling the agent whether to call
   `qmt_xtdata_snapshot`, use an ETF proxy, or ask the user to clarify.
4. Given multiple ETF candidates for the same overseas theme, more liquid or
   larger candidates rank above thinly traded alternatives when relevance is
   otherwise similar.

### US3 - Agent searches sectors before instrument search (P2)

**Acceptance**:
1. Given a sector keyword such as `ETF`, `港股`, or `指数`, `qmt_xtdata_search_sectors` returns matching xtdata sector names.
2. The agent can pass selected sector names into instrument search to narrow the
   universe.

### US4 - Operator refreshes or inspects the cache (P2)

**Acceptance**:
1. The operator can call `qmt_xtdata_refresh_instrument_cache` to rebuild or
   incrementally refresh the cache from bounded sectors.
2. The operator can call `qmt_xtdata_instrument_cache_status` to see cache age,
   source sectors, record counts, and whether built-in seeds are being used.
3. Search remains usable from stale cache if xtdata is temporarily unavailable.

## Functional Requirements

- **FR-001**: Provide `qmt_xtdata_search_instruments` for fuzzy search by code,
  name, alias, pinyin-like ASCII text, sector, market, and instrument type.
- **FR-002**: Provide `qmt_xtdata_resolve_instrument` for "best candidate plus
  ambiguity report" when an agent wants one code to use next.
- **FR-003**: Provide `qmt_xtdata_search_sectors` for fuzzy sector-name search.
- **FR-004**: Provide `qmt_xtdata_refresh_instrument_cache` and
  `qmt_xtdata_instrument_cache_status`.
- **FR-005**: Cache data MUST be persisted by default at
  `/broker/cache/instrument-search-v1.json` or a configurable path under
  `/broker`.
- **FR-006**: Cache writes MUST be atomic and protected by a simple lock to avoid
  corrupting the cache when multiple agents refresh simultaneously.
- **FR-007**: Cache entries MUST include source sector names and refresh
  timestamps so stale or partial results are visible.
- **FR-008**: The default refresh universe MUST be bounded and China-market
  oriented: A shares, Beijing exchange, A-share ETFs, and A-share indices.
  HK-related sectors MAY be included only when explicitly requested or
  configured.
- **FR-009**: Results MUST distinguish `metadata_available` from
  `quote_supported`; an instrument appearing in a sector list does not prove that
  snapshot/bars will work.
- **FR-010**: Search tools MUST be worker-backed and return uniform 002 error
  envelopes.
- **FR-011**: Search must never call quote/history tools for every candidate in
  the hot path. Runtime quote support checks are optional and bounded.
- **FR-012**: Built-in seed data MAY include common broad-market indices, popular
  ETFs, and aliases, but MUST be marked `source: seed` and superseded by xtdata
  cache records.
- **FR-013**: Search and resolve outputs MUST include enough match explanation
  for an agent to avoid blindly trusting a low-confidence match.
- **FR-014**: Search MUST support pinyin-initial/shorthand lookup for Chinese
  instrument names and aliases. Initial matching MUST be case-insensitive and
  punctuation-insensitive.
- **FR-015**: Cache records SHOULD include generated or seeded pinyin initials
  such as `ZGWX` for `中国卫星`. Generated initials MAY be best-effort; seed aliases
  can correct important ambiguous or polyphonic names.
- **FR-016**: Search MUST support ranking modes: `combined`, `relevance`,
  `liquidity`, `size`, `amount`, and `volume`. `combined` is the default.
- **FR-017**: Cache records SHOULD include recent liquidity/size metrics when
  available: latest price, latest amount/volume, rolling average amount/volume,
  total volume/share count, and estimated market value. Missing metrics MUST NOT
  hide otherwise relevant candidates, but MUST lower liquidity/size rank.
- **FR-018**: Liquidity/size metrics MUST be refreshed by bounded batch jobs,
  not by calling history/snapshot for every result in a normal search request.
- **FR-018a**: When historical bar amount/volume is unavailable during refresh,
  the refresh job MAY use bounded snapshot data to populate latest amount/volume
  for ranking. Normal search requests still MUST NOT call quote APIs.
- **FR-019**: For ETF/theme queries, the default `combined` ranking SHOULD
  prefer quote-supported A-share ETF candidates with higher recent turnover and
  broader recognition over low-liquidity lookalikes.
- **FR-020**: Ranking MUST be explainable. Results SHOULD expose which ranking
  factors influenced the final order, such as quote support, type preference,
  liquidity, size, exact name match, pinyin initials, sector/theme match, stale
  metrics, or external-market penalty.
- **FR-021**: Every MCP tool docstring/description MUST be agent-facing and
  operational. It MUST explain when to use the tool, when not to use it, key
  parameters/defaults, cache/ranking semantics, output interpretation, and
  recommended next tools. Generic one-line descriptions are not acceptable.
- **FR-022**: Tool docstrings MUST explicitly warn agents not to invent codes
  when search confidence is low and SHOULD direct them to ask the user to
  clarify or inspect alternates.
- **FR-023**: The feature MUST NOT expose trading, subscription, order, account,
  or write tools.

## Proposed Tool Catalog

- `qmt_xtdata_search_instruments`: fuzzy search over cached/seed instruments.
- `qmt_xtdata_resolve_instrument`: return best match, alternates, and guidance.
- `qmt_xtdata_search_sectors`: fuzzy search over xtdata/cached sector names.
- `qmt_xtdata_refresh_instrument_cache`: refresh cache from selected sectors.
- `qmt_xtdata_instrument_cache_status`: inspect cache freshness and coverage.

## Success Criteria

- **SC-001**: Searching `天岳` returns a valid matching A-share candidate without
  the agent knowing the code in advance.
- **SC-002**: Searching `恒生科技` returns A-share ETF candidates before any HK
  direct-stock candidates, unless the caller explicitly asks for HK direct
  instruments.
- **SC-003**: With xtdata unavailable, search still returns seed/stale-cache
  results and marks cache status as stale or partial.
- **SC-004**: Repeated searches use cache and do not scan all instruments on each
  call.
- **SC-005**: Search results are bounded by `limit` and include no pandas/numpy
  objects.
- **SC-006**: Searching `纳指` returns quote-supported A-share Nasdaq-related ETF
  candidates ordered by default combined rank, with liquidity/size metrics shown
  when available.
- **SC-007**: Searching `ZGWX` returns `中国卫星` as a high-confidence candidate
  with a pinyin-initial match reason.

## Out of Scope

- Global market data enrichment from internet sources.
- Full pinyin segmentation quality comparable to a dedicated Chinese search
  engine.
- Guaranteeing HK/US direct quote support. Search may discover metadata that the
  current QMT runtime cannot quote.
- Postgres-backed instrument master data. JSON cache is sufficient for MVP.

## Assumptions

- xtdata sector and instrument metadata are relatively stable and can be cached.
- For the current appliance, A shares, A-share ETFs, A-share indices, and ETF
  proxies for overseas themes are the reliable default universe.
- HK sector metadata may exist in xtdata, but quote support is runtime-specific
  and should be treated cautiously.
