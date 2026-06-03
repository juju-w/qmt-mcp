# Contract: xtdata MCP Tools

All tools use the 002 error envelope and audit policy. All blocking xtdata calls
run through the 002 worker executor.

## Shared Types

### Code

`code.market`, examples:

- `600000.SH`
- `000001.SZ`
- `510300.SH`

Market-only inputs such as `SH` or `SZ` are allowed only for tools that
explicitly document market-wide behavior.

### Period

Initial required enum:

- `tick`
- `1m`
- `5m`
- `15m`
- `30m`
- `1h`
- `1d`
- `1w`
- `1mon`
- `1q`
- `1hy`
- `1y`

Optional later values may be enabled by runtime capability detection.

### DividendType

- `none`
- `front`
- `back`
- `front_ratio`
- `back_ratio`

Ignored or rejected for periods where xtdata does not apply adjustment.

## `qmt_xtdata_snapshot`

Official API mapping: `xtdata.get_full_tick(code_list)` or equivalent full-tick
snapshot source.

Input:

```json
{
  "codes": ["600000.SH"],
  "fields": []
}
```

Rules:

- `codes` must be non-empty and bounded.
- `fields=[]` means default snapshot fields.
- Tool returns one record per requested code where available.

Output:

```json
{
  "ok": true,
  "data": [
    {
      "code": "600000.SH",
      "time": "2026-06-03T10:00:00+08:00",
      "last_price": 0.0,
      "open": 0.0,
      "high": 0.0,
      "low": 0.0,
      "pre_close": 0.0,
      "volume": 0,
      "amount": 0.0,
      "bid_price": [],
      "bid_volume": [],
      "ask_price": [],
      "ask_volume": [],
      "raw_fields": {}
    }
  ]
}
```

## `qmt_xtdata_download_history`

Official API mapping: `xtdata.download_history_data(...)` or newer
download-history variant when available.

Input:

```json
{
  "code": "600000.SH",
  "period": "1d",
  "start_time": "20250101",
  "end_time": "20250131",
  "incremental": false
}
```

Rules:

- Single code per call for predictable runtime.
- Date range is bounded.
- Returns completion status, not bar data.

Output:

```json
{
  "ok": true,
  "code": "600000.SH",
  "period": "1d",
  "start_time": "20250101",
  "end_time": "20250131",
  "downloaded": true,
  "message": ""
}
```

## `qmt_xtdata_download_history_batch`

Official API mapping: `xtdata.download_history_data2(...)`.

Input:

```json
{
  "codes": ["600000.SH", "000001.SZ"],
  "period": "1d",
  "start_time": "20250101",
  "end_time": "20250131",
  "incremental": null
}
```

Rules:

- Codes are bounded separately from quote-read calls because this tool is meant
  for cache preparation.
- Returns completion status, not bar data.
- Callback-style progress is intentionally not exposed in the request/response
  MVP.

Output:

```json
{
  "ok": true,
  "codes": ["600000.SH", "000001.SZ"],
  "period": "1d",
  "start_time": "20250101",
  "end_time": "20250131",
  "downloaded": true,
  "raw_result": true
}
```

## `qmt_xtdata_bars`

Official API mapping: `xtdata.get_market_data_ex(...)` or local-data equivalent.

Input:

```json
{
  "codes": ["600000.SH"],
  "period": "1d",
  "fields": ["open", "high", "low", "close", "volume", "amount"],
  "start_time": "20250101",
  "end_time": "20250131",
  "count": -1,
  "dividend_type": "none",
  "fill_data": true,
  "enable_read_from_server": true
}
```

Rules:

- `codes`, date range, and effective row count are bounded.
- If history is missing, return an error suggesting `qmt_xtdata_download_history`
  rather than silently downloading.
- `enable_read_from_server` follows compatible xtquant versions; older versions
  that do not accept the argument are called without it.
- Client-supplied `data_dir` is not exposed in the initial MCP surface. If a
  deployment needs it later, it must be restricted to an allowlisted broker data
  root.
- Output is row-oriented JSON, not pandas/numpy objects.

Output:

```json
{
  "ok": true,
  "period": "1d",
  "rows": [
    {
      "code": "600000.SH",
      "time": "2025-01-02",
      "open": 0.0,
      "high": 0.0,
      "low": 0.0,
      "close": 0.0,
      "volume": 0,
      "amount": 0.0
    }
  ]
}
```

## `qmt_xtdata_instrument_detail`

Official API mapping: `xtdata.get_instrument_detail(stock_code, iscomplete)`.

Input:

```json
{
  "code": "600000.SH",
  "complete": false
}
```

Output:

```json
{
  "ok": true,
  "found": true,
  "instrument": {
    "code": "600000.SH",
    "exchange_id": "SH",
    "instrument_id": "600000",
    "name": "",
    "product_id": "",
    "open_date": "",
    "expire_date": null,
    "price_tick": 0.01,
    "up_stop_price": null,
    "down_stop_price": null,
    "is_trading": true,
    "raw_fields": {}
  }
}
```

## `qmt_xtdata_sector_list`

Official API mapping: `xtdata.get_sector_list()`.

Input:

```json
{
  "filter": ""
}
```

Output:

```json
{
  "ok": true,
  "sectors": ["沪深A股"]
}
```

## `qmt_xtdata_sector_constituents`

Official API mapping: `xtdata.get_stock_list_in_sector(...)`.

Input:

```json
{
  "sector": "沪深A股",
  "limit": 5000,
  "real_timetag": -1
}
```

Output:

```json
{
  "ok": true,
  "sector": "沪深A股",
  "codes": ["600000.SH"]
}
```

## `qmt_xtdata_index_weight`

Official API mapping: `xtdata.get_index_weight(index_code)`.

Input:

```json
{
  "index_code": "000300.SH",
  "limit": 5000
}
```

Rules:

- Requires the corresponding xtdata index-weight cache to be available in the
  broker terminal.
- Returns row-oriented code/weight pairs, bounded by `limit`.

Output:

```json
{
  "ok": true,
  "index_code": "000300.SH",
  "weights": [
    {
      "code": "600000.SH",
      "weight": 1.23
    }
  ]
}
```

## `qmt_xtdata_trading_dates`

Official API mapping: `xtdata.get_trading_dates(...)` or calendar equivalent.

Input:

```json
{
  "market": "SH",
  "start_time": "20250101",
  "end_time": "20250131",
  "count": -1
}
```

Output:

```json
{
  "ok": true,
  "market": "SH",
  "dates": ["20250102"],
  "raw_dates": []
}
```

## `qmt_xtdata_trading_calendar`

Official API mapping: `xtdata.get_trading_calendar(...)` when available, with
`xtdata.get_trading_dates(...)` fallback.

Input:

```json
{
  "market": "SH",
  "start_time": "20250101",
  "end_time": "20250131"
}
```

Output:

```json
{
  "ok": true,
  "market": "SH",
  "dates": ["20250102"],
  "raw_dates": []
}
```

## `qmt_xtdata_holidays`

Official API mapping: `xtdata.get_holidays()`.

Input:

```json
{}
```

Output:

```json
{
  "ok": true,
  "dates": ["20250101"]
}
```

## Optional Tools

These are allowed only after runtime compatibility is verified:

- `qmt_xtdata_financial_data`
- `qmt_xtdata_dividend_factors`
- `qmt_xtdata_ipo_info`
- `qmt_xtdata_cb_info`
- `qmt_xtdata_etf_info`

They must follow the same bounded-input and JSON-clean-output rules.
