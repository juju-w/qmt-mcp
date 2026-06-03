# Research: Instrument Search & Symbol Resolution

## Decision: Build Search From xtdata Sector + Detail APIs

Use xtdata's official metadata surface:

- sector list
- sector constituents
- instrument detail

This matches the current permission state because xtdata works and xttrade is
not required.

### Alternatives

- Generic internet search: rejected for MVP because broker/QMT symbol support is
  the key question, not broad web knowledge.
- PostgreSQL master-data table: deferred. The dataset is small enough for JSON
  cache, and the appliance should remain easy to run.
- Search by calling quote tools for every possible code: rejected because it is
  slow, noisy, and may trigger entitlement/rate issues.

## Decision: Cache First, Refresh Explicitly Or When Stale

Instrument names and sector membership are relatively stable. The tool should
use a persistent JSON cache and refresh it explicitly or when stale.

Default TTL: 7 days.

Cache location: `/broker/cache/instrument-search-v1.json`.

## Decision: Seed List Is A Bootstrap Hint

A small built-in seed list is useful for common aliases such as broad-market
indices and popular cross-border ETFs. It should not attempt to be complete.
Every seed result is marked as `source: seed` and can be superseded by xtdata
records.

## Decision: Separate Metadata Discovery From Quote Support

xtdata may list HK sector constituents, but the current wrapper/runtime may not
quote all `.HK` instruments. Therefore every result must distinguish:

- discovered in metadata
- accepted by code validator
- known quote-supported
- unknown quote support

This prevents an agent from assuming that a listed HK stock is safe to pass into
snapshot/bars.

## Decision: Deterministic Scoring First

Use exact, prefix, substring, alias, sector/theme, and type-priority scores.
Avoid ML or heavy Chinese search dependencies in MVP. A later version may add
pinyin support when the dependency story is clear.

## Decision: Keep Relevance Score Separate From Rank Score

Search needs both "does this text match?" and "is this a useful candidate?".
For queries like `纳指`, several ETF names may match. The default result should
prefer candidates with better quote support and liquidity, not only the closest
substring.

Therefore each result has:

- `score`: textual/semantic match score.
- `rank_score`: final sort score after quote support, type priority, and
  liquidity/size signals.

Liquidity and size signals are refreshed in bounded cache jobs. The normal
search request must not fetch bars or snapshots for every candidate.

## Decision: Support Pinyin Initials And ASCII Shorthand

Chinese security search commonly uses first-letter shorthand, especially in
older desktop terminals and among fast keyboard users. It is useful for humans
and also helps agents handle abbreviated user prompts.

MVP should support exact and prefix initials:

- `ZGWX` -> `中国卫星`
- `ZGPA` -> `中国平安`
- `HSKJ` -> `恒生科技`
- `HS300ETF` -> `沪深300ETF`

This should be cache-time normalization, not query-time heavy NLP. Seed aliases
can correct important polyphonic or ambiguous names.

## Other Ranking/Disambiguation Scenarios

The ranking layer should be flexible because similar ambiguity appears in
several places:

- **ETF theme search**: choose high-liquidity ETF proxies before low-liquidity
  lookalikes.
- **Stock vs ETF vs index**: if the query is a theme (`纳指`, `恒生科技`), ETF may
  be more actionable than a direct index; if the query is an exact company name,
  stock should rank higher.
- **A/H/overseas ambiguity**: prefer quote-supported A-share instruments by
  default; mark HK/overseas direct instruments as external or quote-unknown.
- **Near-name collisions**: names sharing a prefix should be ranked by exactness,
  type, liquidity, and status.
- **Inactive or low-activity instruments**: stale, suspended, delisted, or
  extremely low-turnover candidates should be down-ranked or warned.
- **User intent modes**: a future `intent` parameter could express `trade`,
  `observe`, `index_proxy`, `company`, or `sector`, but MVP can cover most cases
  through `types`, `rank_by`, and guidance.
