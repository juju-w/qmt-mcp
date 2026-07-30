# QMT-MCP Reference

Detailed configuration and request examples for **qmt-mcp-ops**.

Protocol baseline: MCP `2026-07-28` is preferred. The same streamable HTTP
endpoint accepts legacy `2025-11-25`, `2025-06-18`, and `2025-03-26` clients.
qmtctl negotiates this automatically through the official Go SDK.

## Environment Variables

### Required server configuration

| Variable | Description |
|---|---|
| `QMT_MCP_AUTH_MODE` | `static` (default), `oauth`, or `hybrid` |
| `QMT_MCP_TOKEN` | Required in static/hybrid; empty is valid in OAuth-only |
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

### OAuth protected resource and JWT verification

| Variable | Default | Description |
|---|---|---|
| `QMT_MCP_PUBLIC_BASE_URL` | empty | Public HTTPS origin used for metadata URL |
| `QMT_MCP_OAUTH_ISSUER` | empty | Exact JWT issuer |
| `QMT_MCP_OAUTH_AUTHORIZATION_SERVERS` | empty | Exactly one URL matching the issuer |
| `QMT_MCP_OAUTH_JWKS_URL` | empty | Explicit bounded signing-key endpoint |
| `QMT_MCP_OAUTH_SCOPES` | all five QMT scopes | Space/comma-separated advertised scopes |
| `QMT_MCP_OAUTH_RESOURCE` | `<public-base>/mcp` | Protected resource identifier |
| `QMT_MCP_OAUTH_RESOURCE_NAME` | `QMT MCP` | Display name |
| `QMT_MCP_OAUTH_ALGORITHMS` | `RS256 ES256` | Allowed asymmetric JWT algorithms |
| `QMT_MCP_OAUTH_CLOCK_SKEW_S` | `30` | JWT time-claim leeway |
| `QMT_MCP_OAUTH_JWKS_TTL_S` | `300` | Signing-key cache TTL |
| `QMT_MCP_OAUTH_HTTP_TIMEOUT_S` | `5` | JWKS request timeout |
| `QMT_MCP_OAUTH_JWKS_MAX_BYTES` | `1048576` | Maximum JWKS response |

OAuth/hybrid requires one secure issuer, authorization server, JWKS URL, and
resource. HTTPS is mandatory except for loopback development. The external AS
issues JWTs; QMT-MCP validates them but never issues tokens.

| Scope | Tool surface |
|---|---|
| `qmt:read` | required core |
| `qmt:market` | read-only xtdata |
| `qmt:account` | xttrade query and portfolio |
| `qmt:manage` | non-trading mutation in an already granted family |
| `qmt:admin` | complete startup-visible surface |

### Tool visibility

| Variable | Default | Description |
|---|---|---|
| `QMT_MCP_TOOL_PROFILE` | `full` | `full`, `readonly`, `market`, `account`, `core`, or `custom` |
| `QMT_MCP_TOOL_ALLOWLIST` | empty | CSV shell globs that further intersect non-core tools |
| `QMT_MCP_TOOL_DENYLIST` | empty | CSV shell globs removed after profile/allowlist selection |

`custom` requires a non-empty allowlist. Core tools always remain available.
Startup visibility is fixed for one server process; restart after changes.
OAuth `tools/list` and `tools/call` additionally intersect it with token scopes.

### MCP paging and HTTP compression

| Variable | Default | Description |
|---|---|---|
| `QMT_MCP_LIST_PAGE_SIZE` | `50` | Server-selected `tools/list` page size, 1 through 1000 |
| `QMT_MCP_GZIP_MIN_SIZE` | `1024` | Minimum eligible JSON response bytes; `0` disables app gzip |

Pagination is applied after startup and OAuth visibility. qmtctl consumes all
pages automatically. SSE is never compressed; set gzip to `0` when a reverse
proxy owns compression.

### MCP durable tasks

| Variable | Default | Description |
|---|---|---|
| `QMT_MCP_TASKS_ENABLED` | `1` | Enable stable `2026-07-28` Tasks for declaring clients |
| `QMT_MCP_TASK_STORE` | `/broker/cache/mcp-tasks-v1.sqlite3` | Persistent single-process SQLite store |
| `QMT_MCP_TASK_TTL_MS` | `86400000` | Task retention TTL; `0` uses no time expiry |
| `QMT_MCP_TASK_POLL_INTERVAL_MS` | `1000` | Client poll guidance, 100 through 60000 ms |
| `QMT_MCP_TASK_MAX_RETAINED` | `1000` | Maximum retained terminal tasks |
| `QMT_MCP_TASK_TOOLS` | six long-running tools | CSV task-capable production tool allowlist |

The store excludes tool arguments, credentials, authorization headers, and raw
principal identifiers. Supported 2025 clients and modern clients that do not
declare Tasks continue synchronous calls.

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
| `QMTCTL_AUTH_STORE` | Optional OAuth session-store path |
| `QMTCTL_TASK_MODE` | `wait` (default), `detach`, or `sync` |
| `QMTCTL_TASK_TIMEOUT` | Overall task wait timeout; default `10m` |

qmtctl credential precedence is explicit flag, access-token env, static-token
env, then saved per-resource OAuth session. Browser login:

```bash
qmtctl auth login \
  --client-id-metadata-url https://client.example.com/qmtctl.json \
  --scope 'qmt:read qmt:market'
qmtctl auth status
qmtctl auth logout
```

For durable long-running calls:

```bash
qmtctl cache refresh --force
qmtctl --task-mode detach --json cache refresh --force
qmtctl task get tsk_<id>
qmtctl task wait tsk_<id>
qmtctl task cancel tsk_<id>
```

`--timeout` applies to one HTTP exchange. `--task-timeout` applies to the
complete wait lifecycle.

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
| `/healthz` | Static bearer or verified JWT | Readiness and family state |
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
