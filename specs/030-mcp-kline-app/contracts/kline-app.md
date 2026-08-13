# Contract: K-Line MCP App

## Tool

`qmt_xtdata_kline_chart`

### Input

```json
{
  "code": "688234.SH",
  "period": "1d",
  "start_time": "",
  "end_time": "",
  "count": 120,
  "dividend_type": "front"
}
```

- `code`: one exact QMT `code.market` value.
- `period`: one of the validated xtdata periods; chart defaults to `1d`.
- `start_time` / `end_time`: `YYYYMMDD[HHmmSS]`, optional.
- `count`: last N rows, `1..1000`, default `120`.
- `dividend_type`: `none`, `front`, `back`, `front_ratio`, or `back_ratio`.

### Tool metadata

```json
{
  "ui": {
    "resourceUri": "ui://qmt-mcp/kline-chart-v1.html",
    "visibility": ["model", "app"]
  }
}
```

The tool retains standard read-only/idempotent/open-world annotations and the
xtdata OAuth scopes `qmt:read` + `qmt:market`.

### Successful structured content

```json
{
  "ok": true,
  "schema_version": "1",
  "instrument": {"code": "688234.SH", "name": "天岳先进"},
  "period": "1d",
  "dividend_type": "front",
  "source": "get_market_data_ex",
  "range": {
    "start": "20260302",
    "end": "20260814",
    "bar_count": 116
  },
  "summary": {
    "latest_close": 136.42,
    "previous_close": 135.0,
    "change": 1.42,
    "change_percent": 1.0519,
    "high": 148.16,
    "low": 110.23
  },
  "bars": [
    {
      "time": "20260302",
      "open": 128.0,
      "high": 131.0,
      "low": 126.0,
      "close": 129.5,
      "volume": 186201,
      "amount": 2590000000
    }
  ]
}
```

`content[0].text` is a short summary, for example:

```text
天岳先进 (688234.SH) 日线：20260302 至 20260814，共 116 根；最新收盘 136.42，较前一根 +1.42 (+1.05%)，区间最高 148.16，最低 110.23。数据源：QMT xtdata。
```

### Error content

Uses the existing envelope:

```json
{
  "ok": false,
  "error_type": "validation|not_ready|dependency|internal",
  "error": "bounded message",
  "details": {}
}
```

The App renders an error state from the same structured content and keeps a
previous successful chart visible for failed interactive refreshes.

## Resource

- URI: `ui://qmt-mcp/kline-chart-v1.html`
- MIME: `text/html;profile=mcp-app`
- Permissions: none
- External connect/resource/frame/base origins: none
- Preferred border: false

The resource is static and versioned. Dynamic market data appears only in the
tool result delivered over the Apps host bridge.
