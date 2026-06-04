# qmtctl

`qmtctl` is a compiled command-line client for the QMT MCP appliance. It is a
thin client over the streamable-http MCP endpoint and does not import `xtquant`
or duplicate broker logic locally.

## Build

```bash
go build -o qmtctl .
```

## Configuration

```bash
export QMT_MCP_URL=http://127.0.0.1:8765/mcp
export QMT_MCP_TOKEN=...
```

Global flags override the environment:

```bash
qmtctl --url http://127.0.0.1:8765/mcp --token "$QMT_MCP_TOKEN" health
```

## Commands

```bash
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
qmtctl smoke
```

`qmtctl smoke --code 510300.SH` adds a live snapshot read to the default health,
tool discovery, and instrument-search checks.
