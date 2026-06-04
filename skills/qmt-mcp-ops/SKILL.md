---
name: qmt-mcp-ops
description: Deploy, operate, and troubleshoot the QMT-MCP appliance. Covers Docker deployment, broker pack management, MCP endpoint usage (xtdata/xttrade tools), qmtctl CLI commands, and the overall architecture/workflow. Use when the user asks about deploying QMT, using MCP tools, running qmtctl commands, configuring broker packs, or troubleshooting the appliance.
---

# QMT-MCP Operations

Broker-agnostic QMT-MCP appliance: run QMT/MiniQMT in Docker (Wine on amd64), expose China A-share market data and read-only account queries to AI agents via MCP.

## Architecture

```
immutable base image  ghcr.io/juju-w/qmt-mcp           mounted at runtime
(Wine wow64 + Win Python 3.12 + MCP + xrdp)  ◄── broker pack → /broker
— broker-neutral, NO terminal/xtquant/account data      (QMT terminal + xtquant + broker.yaml)
```

**Key principle**: switch brokers by swapping the mounted broker pack, never rebuild the image.

### Module layout

```
appliance/          # Dockerfile, compose, scripts, mcp/, brokers/, docs/
├── mcp/
│   ├── qmt_mcp_core/       # MCP server: auth, registry, health, audit, workers
│   ├── qmt_mcp_xtdata/     # Market-data tools (11 tools) + search/cache/index
│   ├── qmt_mcp_xttrade/    # Account-query tools (8 tools, opt-in)
│   └── qmt_mcp_db/         # PostgreSQL persistence (optional)
├── scripts/                 # entrypoint, supervisor, healthcheck, broker detect
└── brokers/                 # broker pack templates
cli/qmtctl/         # Go CLI client (streamable-http MCP)
specs/              # Spec-driven development (001~012)
```

## Deployment

### Prerequisites

- **Native amd64 host** (Apple Silicon = emulation only, QMT may crash on Rosetta AVX)
- Docker + Docker Compose
- QMT terminal installer (`setup_qmt.exe`) + matching `xtquant` RAR from broker

### Step-by-step

```bash
cd appliance

# 1. Configure
cp .env.example .env
# Edit .env: set QMT_MCP_TOKEN (openssl rand -hex 32), BROKER_PACK path

# 2. Build broker-neutral base image
docker compose build

# 3. Create broker pack (extracts terminal + xtquant)
scripts/make-broker-pack.sh <setup_qmt.exe> <xtquant_xxxxxx.rar> brokers/<id>/pack

# 4. Run
docker compose up -d

# 5. (Optional) Enable PostgreSQL persistence
docker compose --profile db up -d
# Set QMT_DB_URL=postgresql://qmt:qmt@db:5432/qmt in .env
```

### Connection endpoints

| Service | Address | Auth |
|---|---|---|
| RDP | `<host>:13389` | `wineuser` / password from `.env` |
| MCP | `http://<host>:18765/mcp` | `Authorization: Bearer <QMT_MCP_TOKEN>` |

### Post-deploy

1. RDP into container, log into QMT terminal with your brokerage account
2. Enable **independent-trading / minimal mode** if account queries are needed
3. MCP autostarts with the desktop session; healthcheck reflects login status

### Multi-broker (one host)

```bash
# One .env per instance (distinct INSTANCE/ports/token/BROKER_PACK)
docker compose --env-file broker-a.env -p qmt-a up -d
docker compose --env-file broker-b.env -p qmt-b up -d
```

## MCP Tools

All tools are **read-only**, bearer-token authenticated, audited (JSONL), return structured JSON.

### Health & capability

| Tool | Purpose |
|---|---|
| `qmt_health` | Overall health (auth, deps, families) |
| `qmt_capabilities` | Feature/capability status |

### xtdata — Market data (11 tools, always on)

| Tool | Purpose |
|---|---|
| `qmt_xtdata_search_instruments` | Fuzzy search by name/code/pinyin/alias/sector/theme |
| `qmt_xtdata_resolve_instrument` | Resolve phrase → best code + alternates |
| `qmt_xtdata_search_sectors` | Fuzzy search sector names |
| `qmt_xtdata_instrument_detail` | Single instrument metadata |
| `qmt_xtdata_snapshot` | Real-time quote (last/bid-ask/volume, up to 50 codes) |
| `qmt_xtdata_bars` | OHLC bars (tick/min/day/week/month, up to 50 codes) |
| `qmt_xtdata_sector_list` | List all sectors |
| `qmt_xtdata_sector_constituents` | Codes in one sector |
| `qmt_xtdata_index_weight` | Index constituent weights |
| `qmt_xtdata_trading_dates` / `_calendar` / `_holidays` | Trading calendar |
| `qmt_xtdata_download_history` / `_batch` | Download history to local cache |
| `qmt_xtdata_instrument_cache_status` / `_refresh_instrument_cache` | Search cache mgmt |

### xttrade — Account queries (8 tools, opt-in)

Enable: `QMT_ENABLE_XTTRADE_QUERY=1` + `QMT_TRADE_ACCOUNTS=<csv>` in `.env`.
Requires broker "programmatic trading" permission (`m_nPythonConnectNet`).

| Tool | Purpose |
|---|---|
| `qmt_xttrade_asset` | Cash/total/market-value/frozen snapshot |
| `qmt_xttrade_positions` | Holdings list |
| `qmt_xttrade_orders` | Today's orders (`cancelable_only` filter) |
| `qmt_xttrade_trades` | Today's fills |
| `qmt_xttrade_position_statistics` | Aggregate stats |
| `qmt_xttrade_account_status` | Account status |
| `qmt_xttrade_new_purchase_limit` | IPO purchase limits |
| `qmt_xttrade_ipo_data` | Today's IPO data (not account-scoped) |

## qmtctl CLI

Compiled Go CLI at `cli/qmtctl/`. Thin client over streamable-http MCP.

```bash
cd cli/qmtctl && go build -o qmtctl .
export QMT_MCP_URL=http://127.0.0.1:18765/mcp
export QMT_MCP_TOKEN=<token>
```

| Command | Example |
|---|---|
| `qmtctl health` | Health check |
| `qmtctl tools` | List registered MCP tools |
| `qmtctl search <query>` | `qmtctl search 天岳 --rank liquidity` |
| `qmtctl resolve <query>` | `qmtctl resolve 纳指 --json` |
| `qmtctl snapshot <codes>` | `qmtctl snapshot 510300.SH 000001.SZ` |
| `qmtctl bars <codes>` | `qmtctl bars 510300.SH --period 1d --start 20250101` |
| `qmtctl cache status` | Search cache freshness |
| `qmtctl cache refresh` | Refresh instrument cache |
| `qmtctl account asset --account <id>` | Account asset |
| `qmtctl account positions --account <id>` | Holdings |
| `qmtctl account orders --account <id> --cancelable-only` | Cancelable orders |
| `qmtctl account trades --account <id>` | Today's fills |
| `qmtctl account status --account <id>` | Account status |
| `qmtctl account statistics --account <id>` | Position stats |
| `qmtctl account purchase-limit --account <id>` | IPO limits |
| `qmtctl account ipo` | IPO data |
| `qmtctl smoke [--code 510300.SH]` | End-to-end smoke test |

Global flags: `--url`, `--token`, `--json`, `--timeout`, `--verbose`.

## Typical workflow

```
1. Deploy appliance (docker compose up)
2. RDP in → log into QMT terminal
3. MCP autostarts → agent connects with bearer token
4. Agent uses search/resolve to find instrument codes
5. Agent uses snapshot/bars for quotes and history
6. (Optional) Agent uses xttrade for read-only account queries
7. (Optional) qmtctl for human CLI access or CI smoke tests
```

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Container exits with code 10-14 | Broker pack issue — check `detect-broker` logs |
| `nodrv_CreateWindow` | Base image tag drifted — pin to date-stamped tag |
| `xttrader.connect()==-1` | Account lacks `m_nPythonConnectNet` permission |
| MCP unhealthy | RDP login pending — log in to start the desktop session |
| UnicodeDecodeError | Missing `zh_CN.GBK` locale — image builds with it by default |
| `not_authorized` on xttrade | Enable flag + allowlist in `.env`, or broker permission missing |

## Security essentials

- Bearer token in `.env` only (git-ignored), never baked into images
- Trading credentials only in interactive QMT session, never in config
- MCP is read-only by design — no write/order/cancel/transfer tools
- Run `scripts/harden-check.sh` before any non-loopback deployment
- RDP: bind to loopback, tunnel via VPN/SSH; never expose publicly

## Additional resources

- For detailed tool parameters and architecture decisions, see [reference.md](reference.md)
- Broker pack guide: `appliance/docs/BROKER-PACK.md`
- Deploy & hardening: `appliance/docs/DEPLOY.md`
- AI agent collaboration guide: `AGENT.md`
