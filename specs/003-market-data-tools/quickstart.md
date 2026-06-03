# Quickstart: xtdata Market-Data Tools

Goal: validate the first real MCP tool family with the current permission state.

## 1. Start appliance and log into QMT

```bash
cd qmt-wine-rdp
docker compose up -d
```

Log into QMT manually over RDP. xttrade permission is not required.

## 2. Check capabilities

Call `qmt_capabilities`.

Expected:

- `xtdata` is `enabled` or `not_ready`
- `xttrade_query` may be `not_authorized`
- no write/trade tools appear

## 3. Snapshot smoke

Call:

```text
qmt_xtdata_snapshot({"codes":["510300.SH"]})
```

Expected: structured quote/tick output or a uniform `not_ready` dependency error.

## 4. Download then read bars

Call:

```text
qmt_xtdata_download_history({
  "code": "510300.SH",
  "period": "1d",
  "start_time": "20250101",
  "end_time": "20250131"
})
```

For bounded batch cache preparation:

```text
qmt_xtdata_download_history_batch({
  "codes": ["510300.SH", "159919.SZ"],
  "period": "1d",
  "start_time": "20250101",
  "end_time": "20250131",
  "incremental": null
})
```

Then:

```text
qmt_xtdata_bars({
  "codes": ["510300.SH"],
  "period": "1d",
  "fields": ["open", "high", "low", "close", "volume", "amount"],
  "start_time": "20250101",
  "end_time": "20250131",
  "count": -1,
  "dividend_type": "none"
})
```

Expected: JSON-clean rows with no pandas/numpy serialization artifacts.

## 5. Reference data smoke

Call:

```text
qmt_xtdata_instrument_detail({"code":"510300.SH","complete":false})
qmt_xtdata_sector_list({})
qmt_xtdata_trading_dates({"market":"SH","start_time":"20250101","end_time":"20250131"})
qmt_xtdata_trading_calendar({"market":"SH","start_time":"20250101","end_time":"20250131"})
qmt_xtdata_index_weight({"index_code":"000300.SH","limit":5000})
```

Expected: structured metadata/list responses or clear not-supported errors.
