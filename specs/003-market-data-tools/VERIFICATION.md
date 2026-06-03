# 003 Market-Data Tools — Live Verification

**Date**: 2026-06-03
**Image**: `qmt-appliance-base:local` (pinned base + `zh_CN.GBK` Wine prefix)
**Broker pack**: 光大金阳光 (XtItClient 投研版, 独立交易); xtquant `xtquant_250807`
**Method**: in-process — build `qmt_mcp_core.app.create_app(enable_xtdata=True)`,
invoke each registered tool's callable against the running QMT (xtdata live).

## Result: 11/11 xtdata tools working with real structured data

| Tool | Result |
|---|---|
| qmt_xtdata_snapshot | ✅ `000001.SZ` last_price + 5-level book |
| qmt_xtdata_bars | ✅ real daily OHLCV rows |
| qmt_xtdata_download_history | ✅ `downloaded: true` |
| qmt_xtdata_download_history_batch | ✅ |
| qmt_xtdata_instrument_detail | ✅ `平安银行` + 涨跌停/流通股本 |
| qmt_xtdata_trading_dates | ✅ normalized `YYYYMMDD` |
| qmt_xtdata_trading_calendar | ✅ |
| qmt_xtdata_holidays | ✅ |
| qmt_xtdata_index_weight | ✅ |
| **qmt_xtdata_sector_list** | ✅ Chinese sectors decode (上证A股/创业板/沪市ETF…) — **fixed by zh_CN.GBK** |
| **qmt_xtdata_sector_constituents** | ✅ `沪深A股` → `[600051.SH, …]` |

## Key fixes that made this pass
- Base image **pinned by digest** → healthy Wine prefix (no `nodrv_CreateWindow`).
- Wine prefix built/run under **`zh_CN.GBK` (cp936)** → `get_sector_list` & other
  Chinese-file paths decode instead of `UnicodeDecodeError`/`charmap`.
- Structured serializers return JSON-clean output (no pandas/numpy/SDK leakage).
- Tools degrade gracefully (`not_ready`/`dependency`) instead of crashing the server.

## Not covered here (separate)
- Streamable HTTP transport (`/mcp`) + bearer-token end-to-end via an external MCP client (002 US1). SSE is now a compatibility fallback only.
- Account/trade tools (004) — blocked on broker `m_nPythonConnectNet` permission.
- Real-time subscription/streaming — deferred by design.
