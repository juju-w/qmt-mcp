# QMT-MCP Reference

Detailed reference for the qmt-mcp-ops skill.

## Environment variables

### Required

| Variable | Description |
|---|---|
| `QMT_MCP_TOKEN` | Bearer token for MCP auth. Generate: `openssl rand -hex 32` |
| `BROKER_PACK` | Host path to broker pack directory |

### Optional

| Variable | Default | Description |
|---|---|---|
| `INSTANCE` | `default` | Container name suffix (`qmt-<INSTANCE>`) |
| `RDP_PORT` | `13389` | Host RDP port (container: 3389) |
| `MCP_PORT` | `18765` | Host MCP port (container: 8765) |
| `QMT_RDP_PASSWORD` | `qmt` | RDP password for `wineuser` — **change for prod** |
| `QMT_DB_URL` | _(empty)_ | PostgreSQL DSN for persistence (012) |
| `QMT_DB_USER` | `qmt` | Bundled DB user (with `--profile db`) |
| `QMT_DB_PASSWORD` | `qmt` | Bundled DB password |
| `QMT_DB_NAME` | `qmt` | Bundled DB name |
| `QMT_ENABLE_XTTRADE_QUERY` | `0` | Enable read-only account queries (004) |
| `QMT_TRADE_ACCOUNTS` | _(empty)_ | CSV of allowed account IDs |

## Broker pack structure

```
<pack>/
├── broker.yaml                 # optional config (schema v1)
├── bin.x64/XtItClient.exe      # broker's QMT terminal
├── userdata_mini/              # created at login
├── xtquant/                    # matching xtquant package
└── ...
```

### `broker.yaml` schema (v1)

All fields optional; omitted → auto-detected by `detect-broker`.

```yaml
schema_version: 1
broker: { id: my-broker, name: 我的券商 QMT }
terminal: { client: bin.x64/XtItClient.exe, userdata: userdata_mini }
xtquant:  { path: xtquant }
mcp:      { mode: readonly }   # readonly (default) | trade (deferred)
```

### detect-broker exit codes

| Code | Meaning |
|---|---|
| 10 | `/broker` empty/unreadable |
| 11 | `broker.yaml` malformed |
| 12 | Explicit path doesn't exist |
| 13 | Client unresolved (set `terminal.client`) |
| 14 | xtquant unresolved (set `xtquant.path`) |

## Tool parameter details

### search_instruments

```json
{
  "query": "天岳",
  "sectors": ["沪深A股"],
  "markets": ["SH", "SZ"],
  "types": ["stock"],
  "limit": 20,
  "rank_by": "combined",     // combined | liquidity | relevance
  "refresh": "stale",        // stale | force | never
  "include_external": false,
  "include_metrics": true
}
```

### resolve_instrument

```json
{
  "query": "纳指",
  "prefer_types": ["ETF"],
  "rank_by": "combined",
  "min_score": 70,
  "limit": 5,
  "refresh": "stale"
}
```

### snapshot

```json
{
  "codes": ["510300.SH", "000001.SZ"],
  "fields": ["lastPrice", "bidPrice", "askPrice"]  // optional filter
}
```

### bars

```json
{
  "codes": ["510300.SH"],
  "period": "1d",            // tick/1m/5m/15m/30m/1h/1d/1w/1mon
  "fields": ["open","high","low","close","volume","amount"],
  "start_time": "20250101",
  "end_time": "20250110",
  "count": -1,               // -1 = all, else last N (max 10000)
  "dividend_type": "none",   // none/front/back/front_ratio/back_ratio
  "fill_data": true,
  "enable_read_from_server": true
}
```

### download_history

```json
{
  "code": "510300.SH",
  "period": "1d",
  "start_time": "20240101",
  "end_time": "",
  "incremental": false
}
```

Batch version: `codes` (list, max 200), same period/time args.

## Docker Compose profiles

| Profile | Service | Description |
|---|---|---|
| _(default)_ | `qmt` | Core appliance only |
| `db` | `db` | Bundled PostgreSQL 16 |

```bash
# Default (no DB)
docker compose up -d

# With bundled PostgreSQL
docker compose --profile db up -d
```

## Health endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `/healthz` | Bearer token | Full health (families, deps, readiness) |
| `/livez` | None | Liveness probe (for Docker HEALTHCHECK) |

## Gotchas (from AGENT.md)

1. **Pin base image to date-stamped tag** (e.g. `stable-11.0-20260531`). Never use floating `:stable` — different base produces broken Wine prefixes (`nodrv_CreateWindow`).
2. **GBK locale**: QMT is cp936 Chinese. Image uses `zh_CN.GBK`; without it, `get_sector_list` etc. crash on Chinese file paths.
3. **Resolved env values need single quotes**: Wine paths have backslashes; without quotes, bash `source` eats them.
4. **Trading permission**: `xttrader.connect()==-1` is usually missing broker permission, not a code bug.
5. **Client priority**: `detect-broker` prefers `XtItClient.exe` (research edition) over standalone `XtMiniQmt.exe`.
6. **Storage**: broker pack must be on real disk, never tmpfs (RAM exhaustion risk).
7. **Python 3.12 fixed**: `xtquant` officially supports up to 3.12 only.
