# qmtctl

`qmtctl` is the compiled command-line client for QMT-MCP. It uses the official
MCP Go SDK, prefers stable MCP `2026-07-28`, and automatically falls back to the
supported 2025 initialize/session flow. It never imports `xtquant` or duplicates
broker logic locally.

`qmtctl tools` follows every standard `tools/list` cursor and presents one
complete catalog. It also uses Go's standard transparent gzip negotiation and
decoding. There is no paging or compression flag, and single-page servers keep
the same output.

Building from source requires Go 1.25 or newer:

```bash
go build -o qmtctl .
```

## Authentication

Set the resource URL once:

```bash
export QMT_MCP_URL=https://qmt.example.com/mcp
```

Static bearer:

```bash
export QMT_MCP_TOKEN=<token>
qmtctl health
```

Existing OAuth access token:

```bash
export QMT_MCP_ACCESS_TOKEN=<access-token>
qmtctl health
```

Browser Authorization Code + PKCE login, preferably with a Client ID Metadata
Document:

```bash
qmtctl auth login \
  --client-id-metadata-url https://client.example.com/qmtctl.json \
  --scope 'qmt:read qmt:market'
```

Preregistered public client:

```bash
qmtctl auth login --client-id qmtctl-public \
  --scope 'qmt:read qmt:market qmt:account'
```

Dynamic client registration is a deprecated compatibility path and must be
selected explicitly:

```bash
qmtctl auth login --dynamic-registration
```

Use `--no-browser` on a headless shell; qmtctl prints the authorization URL and
continues listening on a loopback callback. `--login-timeout` defaults to five
minutes.

Sessions are keyed by canonical resource and saved in the OS user configuration
directory. On Unix, the directory is 0700 and the file is 0600. Access and
refresh token rotation is written atomically; client secrets are never saved.

```bash
qmtctl auth discover --json
qmtctl auth status
qmtctl auth logout
```

`auth status` never prints token material. Override the store with
`QMTCTL_AUTH_STORE` or `--auth-store`.

Credential precedence is:

1. `--access-token` / `--token`
2. `QMT_MCP_ACCESS_TOKEN`
3. `QMT_MCP_TOKEN`
4. saved OAuth session for the resource
5. unauthenticated request

Global flags override environment configuration:

```bash
qmtctl --url https://qmt.example.com/mcp --access-token "$TOKEN" health
qmtctl --url http://127.0.0.1:8765/mcp --token "$QMT_MCP_TOKEN" health
```

## Commands

```bash
qmtctl version
qmtctl auth discover
qmtctl auth login --client-id qmtctl-public --scope 'qmt:read qmt:market'
qmtctl auth status
qmtctl auth logout
qmtctl health
qmtctl tools
qmtctl search 天岳
qmtctl resolve 纳指 --rank liquidity --json
qmtctl snapshot 510300.SH
qmtctl snapshot --cache-only 510300.SH
qmtctl bars 510300.SH --period 1d --start 20250101 --end 20250110
qmtctl cache status
qmtctl cache refresh
qmtctl subscription add --id strategy1 510300.SH,510500.SH
qmtctl subscription status
qmtctl subscription list
qmtctl subscription remove --id strategy1
qmtctl account asset --account 123456789
qmtctl account positions --account 123456789
qmtctl account orders --account 123456789 --cancelable-only
qmtctl account trades --account 123456789
qmtctl account status --account 123456789
qmtctl account statistics --account 123456789
qmtctl account purchase-limit --account 123456789
qmtctl account ipo
qmtctl portfolio summary --account 123456789
qmtctl portfolio positions --account 123456789 --quote-policy live
qmtctl portfolio exposure --account 123456789
qmtctl portfolio risk --account 123456789 --max-single-weight 0.3
qmtctl option chain --family 300ETF
qmtctl option quotes 10000001.SHO,10000002.SHO
qmtctl option vix-inputs --family 300ETF
qmtctl ref financial 600000.SH --tables Income,CashFlow --start 20250101
qmtctl ref ipo --start 20250101 --end 20250131
qmtctl ref dividends 510300.SH
qmtctl sector create MCP/strategy1/latest-signal
qmtctl sector import-json --sector MCP/strategy1/latest-signal --file result.json
qmtctl formula call --formula VIX_HELPER --code 510300.SH
qmtctl formula generate --formula VIX_HELPER --result-path vix.feather
qmtctl smoke
```

`qmtctl smoke --code 510300.SH` adds a live snapshot to the default health, tool
discovery, and instrument-search checks. OAuth-visible commands depend on the
granted scopes and the server's startup Profile and feature gates.
