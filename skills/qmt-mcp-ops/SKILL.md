---
name: qmt-mcp-ops
description: Deploy, operate, and troubleshoot the QMT-MCP appliance and qmtctl. Covers broker packs, static bearer and OAuth protected-resource discovery, market subscriptions, account and portfolio queries, options, reference data, managed sectors, formula runtime, and CLI usage. Use for QMT MCP operations, client access, capability discovery, or appliance troubleshooting.
---

# QMT-MCP Operations

Operate the broker-neutral QMT appliance: Wine runs Windows QMT on native amd64,
and streamable HTTP MCP exposes xtdata plus gated account and analysis features.

For first deployment and deployment failures, use
**deploying-qmt-mcp-appliance**. For repository development, CI, and release
rules, follow `AGENT.md`.

## Architecture

```text
ghcr.io/juju-w/qmt-mcp                 runtime mount
Wine + Python 3.12 + MCP           <-- /broker
broker-neutral image                   QMT + xtquant + broker.yaml + userdata
```

Switch brokers by mounting a different broker pack. Never bake a terminal,
credentials, account data, or a personal strategy into the image.

```text
appliance/mcp/
  qmt_mcp_core/       auth, OAuth metadata, registry, health, audit, workers
  qmt_mcp_xtdata/     market, search, subscriptions, options, reference, sectors, formulas
  qmt_mcp_xttrade/    read-only account queries
  qmt_mcp_portfolio/  read-only portfolio analytics
  qmt_mcp_db/         optional PostgreSQL persistence
cli/qmtctl/           compiled streamable HTTP client
specs/001-018/        feature specifications
```

## Deploy

Requirements: native amd64 Linux, Docker Compose, and a broker pack containing
the QMT terminal plus matching xtquant.

```bash
cd appliance
cp .env.example .env
# Set a strong QMT_MCP_TOKEN and BROKER_PACK.
docker compose up -d
```

Optional PostgreSQL:

```bash
docker compose --profile db up -d
```

After every create or restart, RDP to `<host>:13389` and log into QMT. The MCP
server autostarts with that desktop session. The endpoint is
`http://<host>:18765/mcp`; use TLS for any non-local connection.

Run multiple brokers with one env file, project name, and port pair per
instance:

```bash
docker compose --env-file broker-a.env -p qmt-a up -d
docker compose --env-file broker-b.env -p qmt-b up -d
```

## Authentication

| Mode | Server responsibility | Client credential |
|---|---|---|
| Static bearer | Validate `QMT_MCP_TOKEN` | `QMT_MCP_TOKEN` / `--token` |
| OAuth discovery | Publish Protected Resource Metadata and 401 challenge | Existing `QMT_MCP_ACCESS_TOKEN` / `--access-token` |

The server does not implement browser login, authorization-code exchange,
refresh, dynamic registration, or JWT/JWKS validation. A production OAuth
authorization server or gateway must issue and validate the access token. See
`docs/MCP-CLIENTS.md` for Codex, Claude Code, WorkBuddy, and OAuth setup.

## Tool Families

The standard registry has 37 tools:

| Family | Count | Availability |
|---|---:|---|
| Core health/capabilities | 2 | Always |
| Market/search/history | 16 | Default |
| Quote subscription cache | 4 | Default |
| Option/volatility inputs | 6 | Default |
| Financial/reference data | 9 | Default, runtime capability degradation |

Optional families bring the maximum registry to 63 tools:

| Family | Count | Gate |
|---|---:|---|
| xttrade account queries | 8 | `QMT_ENABLE_XTTRADE_QUERY=1` and `QMT_TRADE_ACCOUNTS` |
| Portfolio analytics | 4 | Automatically available with an enabled trader session |
| Managed sector writes | 7 | `QMT_ENABLE_XTDATA_SECTOR_WRITE=1` and managed prefixes |
| Formula/factor runtime | 7 | `QMT_ENABLE_FORMULA_RUNTIME=1`, allowlist, output sandbox |

Market data, account queries, options, reference data, and portfolio analysis
are read-only. Sector and formula families can mutate QMT-managed state or write
factor output, so they are disabled by default and constrained server-side.

Important workflows:

- Resolve a phrase with search/resolve before requesting snapshot or bars.
- A quote subscription uses official `subscribe_quote` when available and a
  bounded polling fallback otherwise; snapshot can prefer or require hot cache.
- `volatility_index_inputs` returns normalized option-chain inputs, not an
  official volatility index value.
- Portfolio analysis depends on a permitted xttrade account and available
  quotes.
- Sector operations may touch only configured prefixes such as `MCP/` or `AI/`.
- Formula calls may use only allowlisted formulas and sandboxed output paths.

## qmtctl

Download the matching qmtctl archive from the GitHub Release for Linux, macOS,
or Windows on amd64/arm64, or build from source:

```bash
cd cli/qmtctl
go build -o qmtctl .
export QMT_MCP_URL=http://127.0.0.1:18765/mcp
export QMT_MCP_TOKEN=<token>
```

For an OAuth or gateway-issued bearer:

```bash
export QMT_MCP_ACCESS_TOKEN=<access-token>
qmtctl auth discover --json
qmtctl health
```

`QMT_MCP_ACCESS_TOKEN` takes precedence over `QMT_MCP_TOKEN`. Equivalent global
flags are `--url`, `--access-token`/`--token`, `--json`, and `--timeout`.

| Command family | Typical use |
|---|---|
| `version`, `auth`, `health`, `tools`, `smoke` | Version, discovery, connectivity, registry |
| `search`, `resolve`, `snapshot`, `bars`, `cache` | Instrument and market data |
| `subscription` | Add, remove, list, and inspect quote subscriptions |
| `account` | Read-only asset, position, order, trade, status, IPO queries |
| `portfolio` | Summary, enriched positions, exposure, risk checks |
| `option` | Underlyings, chains, details, quotes, IV, VIX inputs |
| `ref` | Financials, IPO, dividends, convertible bonds, ETF metadata |
| `sector` | Gated managed-sector create/import/update/delete |
| `formula` | Gated calls, factor generation, subscriptions, cache |

Use `qmtctl <family> --help` for exact arguments. Representative calls:

```bash
qmtctl snapshot --cache-only 510300.SH
qmtctl subscription add --id strategy1 510300.SH,510500.SH
qmtctl portfolio risk --account 123456789 --max-single-weight 0.3
qmtctl option vix-inputs --family 300ETF
qmtctl ref financial 600000.SH --tables Income,CashFlow --start 20250101
qmtctl sector import-json --sector MCP/strategy1/latest-signal --file result.json
qmtctl formula generate --formula VIX_HELPER --result-path vix.feather
qmtctl smoke --code 510300.SH
```

## Troubleshooting

| Symptom | Likely cause / action |
|---|---|
| Exit code 10-14 | Broker-pack discovery failure; inspect `detect-broker` logs |
| `nodrv_CreateWindow` | Wine base drift or damaged prefix; use the pinned date tag |
| `/livez` is silent after restart | RDP session has not started MCP autostart |
| `xttrader.connect()==-1` | Broker has not enabled external/programmatic trading |
| `not_authorized` on account tools | Flag, account allowlist, or broker permission missing |
| OAuth discovery works but calls return 401 | Gateway/token validation is not wired to the bearer gate |
| Chinese path decoding fails | Image or prefix is missing `zh_CN.GBK` |

## Security

- Keep bearer credentials only in gitignored environment files or secret stores.
- Put remote MCP behind HTTPS; bind RDP locally and reach it through VPN/SSH.
- Run `appliance/scripts/harden-check.sh` before non-loopback deployment.
- Keep destructive trading tools out of the default surface.
- Do not commit broker binaries, account identifiers, `.env`, or personal
  strategy data.

## Resources

- Detailed configuration and request examples: [reference.md](reference.md)
- qmtctl command reference: `cli/qmtctl/README.md`
- MCP client and OAuth setup: `docs/MCP-CLIENTS.md`
- Broker pack: `appliance/docs/BROKER-PACK.md`
- Deployment hardening: `appliance/docs/DEPLOY.md`
- Release and cache operations: `docs/RELEASE.md`
- Canonical development rules: `AGENT.md`
