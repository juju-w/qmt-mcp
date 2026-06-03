# Data Model: xtdata Market-Data Tools

## XtDataCapability

| Field | Type | Notes |
|---|---|---|
| `state` | enum | `enabled`, `not_ready`, `error`, `disabled`. |
| `xtquant_version` | string? | Runtime-discovered if available. |
| `supports_optional` | object | Optional dataset/tool support flags. |
| `reason` | string | Sanitized explanation. |

## InstrumentCode

| Field | Type | Notes |
|---|---|---|
| `code` | string | Numeric/symbol part. |
| `market` | enum/string | `SH`, `SZ`, `BJ`, etc. |
| `normalized` | string | `code.market`. |

Validation:

- Required format for instrument tools: `code.market`.
- Market-only values allowed only for explicitly market-wide tools.

## BarRequest

| Field | Type | Notes |
|---|---|---|
| `codes` | list[InstrumentCode] | Bounded. |
| `period` | enum | Required period enum. |
| `fields` | list[string] | Empty means default. |
| `start_time` | string | `YYYYMMDD` or compatible datetime. |
| `end_time` | string | Same format. |
| `count` | integer | Bounded; `-1` allowed only with bounded date range. |
| `dividend_type` | enum | Applies to K-line periods. |

## SnapshotRecord

Normalized quote/tick output:

- code
- time
- last_price
- open/high/low/pre_close
- volume/amount
- bid/ask price and volume arrays
- raw_fields for unmapped safe fields

## BarRow

Normalized historical/local row:

- code
- time
- open/high/low/close
- volume/amount
- optional requested fields

## InstrumentDetail

Core fields:

- code
- exchange_id
- instrument_id
- name
- product_id/product_name
- open_date/expire_date
- price_tick
- up/down stop price
- is_trading
- raw_fields for safe extra metadata

## ReferenceList

Used for sector, calendar, holiday, and optional metadata lists. Always includes:

- source/tool name
- query parameters
- bounded list of normalized records
- `truncated` flag when output limit is reached
