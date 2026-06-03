# Verification: Instrument Search Tools

Date: 2026-06-03

## Local Fake xtdata Smoke

Ran a local fake `xtquant.xtdata` registration smoke through the real MCP
registry and worker wrapper.

Covered:

- `qmt_xtdata_refresh_instrument_cache`
- `qmt_xtdata_search_instruments`
- `qmt_xtdata_resolve_instrument`
- `qmt_xtdata_search_sectors`
- `qmt_xtdata_instrument_cache_status`

Assertions:

- `ZGWX` resolves to `600118.SH`.
- `zgpa` resolves to `601318.SH`.
- `纳指` with `types=["etf"]` and `rank_by="liquidity"` orders seeded higher
  liquidity ETF candidates first.
- `恒生科技` with `prefer_types=["etf"]` returns `513130.SH` as best.
- Tool descriptions are present and agent-facing.

## Live Container Smoke

Environment:

- Container: `qmt-guangda`
- Transport: `streamable-http`
- Endpoint: `http://127.0.0.1:8765/mcp`
- Cache path: `/broker/cache/instrument-search-v1.json`
- Broker pack runtime: Wine Python + MiniQMT xtdata

Results:

- MCP tool discovery returned 18 tools, including the five 006 tools.
- Forced cache refresh completed with `record_count=7757`,
  `sector_count=7077`, `partial=false`, and no refresh errors.
- Search `天岳` returned `688234.SH`.
- Resolve `恒生科技` returned best candidate `513130.SH`. The live resolver
  correctly marked confidence as ambiguous when multiple ETF products were
  close, while still exposing the best candidate and alternates for the agent.
- Search `ZGWX` returned `600118.SH` with
  `pinyin_initials_exact:ZGWX`.
- Search `纳指` with `types=["etf"]` and `rank_by="liquidity"` used snapshot
  liquidity fallback when bar amount/volume was unavailable. On the live quote
  at verification time, the top results were ordered by latest amount:
  `159941.SZ`, `159509.SZ`, `513100.SH`, `159501.SZ`, `159660.SZ`.
- Calling `qmt_xtdata_snapshot` and `qmt_xtdata_bars` with the selected
  `恒生科技` best candidate succeeded.

Notes:

- Wine Python displays Chinese text as mojibake in the SSH terminal, but the
  MCP JSON payloads and matching behavior remain correct.
- Bar-based liquidity metrics are attempted first. If xtdata returns no valid
  amount/volume rows, refresh falls back to bounded `get_full_tick` snapshot
  metrics and normal searches still use only the cache.
