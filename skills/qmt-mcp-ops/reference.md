# QMT-MCP Reference

Detailed configuration and request examples for **qmt-mcp-ops**.

## Environment Variables

### Required server configuration

| Variable | Description |
|---|---|
| `QMT_MCP_TOKEN` | Static bearer secret accepted by the MCP server |
| `BROKER_PACK` | Host path to the QMT terminal, matching xtquant, and optional `broker.yaml` |

Generate a static token with `openssl rand -hex 32`.

### Runtime and persistence

| Variable | Default | Description |
|---|---|---|
| `INSTANCE` | `default` | Container suffix |
| `RDP_PORT` | `13389` | Host RDP port |
| `MCP_PORT` | `18765` | Host MCP port |
| `QMT_RDP_PASSWORD` | `qmt` | RDP password; change outside development |
| `QMT_DB_URL` | empty | PostgreSQL DSN; empty disables persistence |
| `QMT_DB_USER` / `QMT_DB_PASSWORD` / `QMT_DB_NAME` | `qmt` | Bundled `db` profile settings |

### OAuth protected-resource metadata

| Variable | Default | Description |
|---|---|---|
| `QMT_MCP_PUBLIC_BASE_URL` | empty | Public HTTPS origin used for metadata URL |
| `QMT_MCP_OAUTH_AUTHORIZATION_SERVERS` | empty | CSV authorization-server issuer URLs |
| `QMT_MCP_OAUTH_SCOPES` | `qmt:read` | Space or comma separated supported scopes |
| `QMT_MCP_OAUTH_RESOURCE` | `<public-base>/mcp` | Protected resource identifier |
| `QMT_MCP_OAUTH_RESOURCE_NAME` | `QMT MCP` | Display name |

These variables publish discovery metadata; they do not add an authorization
server or JWT verifier.

### Feature gates

| Variable | Default | Description |
|---|---|---|
| `QMT_ENABLE_XTTRADE_QUERY` | `0` | Enable read-only account tools |
| `QMT_TRADE_ACCOUNTS` | empty | CSV server-side account allowlist |
| `QMT_ENABLE_XTDATA_SECTOR_WRITE` | `0` | Enable managed custom-sector mutation |
| `QMT_XTDATA_SECTOR_WRITE_PREFIXES` | `MCP/,AI/` | Writable sector namespace prefixes |
| `QMT_ENABLE_FORMULA_RUNTIME` | `0` | Enable formula/factor runtime |
| `QMT_FORMULA_ALLOWLIST` | empty | CSV formulas the runtime may invoke |
| `QMT_FORMULA_OUTPUT_SANDBOX` | `/broker/formula-output` | Allowed generated-output root |

### Quote subscription cache

| Variable | Default | Description |
|---|---|---|
| `QMT_QUOTE_SUBSCRIPTION_STORE` | `/broker/cache/quote-subscriptions-v1.json` | Persistent subscription definitions |
| `QMT_QUOTE_CACHE_MAX_AGE_MS` | `10000` | Freshness threshold for cached snapshot reads |
| `QMT_QUOTE_SUBSCRIPTION_MAX_CODES` | `100` | Total code limit |
| `QMT_QUOTE_SUBSCRIPTION_MAX_OFFICIAL` | `50` | Official callback subscription limit |
| `QMT_QUOTE_SUBSCRIPTION_MIN_FALLBACK_INTERVAL_S` | `5` | Minimum polling fallback interval |

### qmtctl client

| Variable | Description |
|---|---|
| `QMT_MCP_URL` | MCP URL ending in `/mcp` |
| `QMT_MCP_ACCESS_TOKEN` | Existing OAuth/gateway token; highest precedence |
| `QMT_MCP_TOKEN` | Static bearer fallback |

## Broker Pack

```text
<pack>/
  broker.yaml
  bin.x64/XtItClient.exe
  userdata_mini/
  xtquant/
```

All `broker.yaml` fields are optional; omitted fields are auto-detected:

```yaml
schema_version: 1
broker: { id: my-broker, name: 我的券商 QMT }
terminal: { client: bin.x64/XtItClient.exe, userdata: userdata_mini }
xtquant: { path: xtquant }
mcp: { mode: readonly }
```

| Exit | Meaning |
|---:|---|
| 10 | `/broker` empty or unreadable |
| 11 | `broker.yaml` malformed |
| 12 | Explicit path missing |
| 13 | Terminal client unresolved |
| 14 | xtquant unresolved |

## Selected Tool Requests

Search:

```json
{
  "query": "天岳",
  "sectors": ["沪深A股"],
  "markets": ["SH", "SZ"],
  "types": ["stock"],
  "limit": 20,
  "rank_by": "combined",
  "refresh": "stale",
  "include_external": false,
  "include_metrics": true
}
```

Snapshot:

```json
{
  "codes": ["510300.SH", "000001.SZ"],
  "fields": ["lastPrice", "bidPrice", "askPrice"],
  "cache_policy": "prefer"
}
```

Bars:

```json
{
  "codes": ["510300.SH"],
  "period": "1d",
  "fields": ["open", "high", "low", "close", "volume", "amount"],
  "start_time": "20250101",
  "end_time": "20250110",
  "count": -1,
  "dividend_type": "none",
  "fill_data": true,
  "enable_read_from_server": true
}
```

Quote subscription:

```json
{
  "subscription_id": "strategy1",
  "codes": ["510300.SH", "510500.SH"],
  "period": "tick",
  "fallback_interval_seconds": 5
}
```

Download history:

```json
{
  "code": "510300.SH",
  "period": "1d",
  "start_time": "20240101",
  "end_time": "",
  "incremental": false
}
```

Use the batch variant for up to 200 codes, then call bars to read the result.

## Compose Profiles And Health

| Profile | Service |
|---|---|
| default | Core QMT appliance |
| `db` | Appliance plus PostgreSQL 16 |

```bash
docker compose up -d
docker compose --profile db up -d
```

| Endpoint | Auth | Purpose |
|---|---|---|
| `/livez` | None | Minimal liveness |
| `/healthz` | Bearer | Readiness and family state |
| `/.well-known/oauth-protected-resource` | None | Optional OAuth resource metadata |

## Operational Constraints

1. Pin the Wine base to a date-stamped tag; do not use floating `stable`.
2. Keep Python at 3.12 because the proprietary xtquant extension targets it.
3. Build the Wine prefix with `zh_CN.GBK` for Chinese QMT paths.
4. Quote resolved Wine paths when shell-sourcing generated env files.
5. Keep broker packs on real disk, never tmpfs.
6. Treat `xttrader.connect()==-1` as a likely broker permission issue.
7. Prefer `XtItClient.exe` when both QMT executables exist.
8. Follow the canonical repository rules in `AGENT.md`; release mechanics live
   in `docs/RELEASE.md`.
