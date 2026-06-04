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
qmtctl bars 510300.SH --period 1d --start 20250101 --end 20250110
qmtctl cache status
qmtctl cache refresh
qmtctl smoke
```

`qmtctl smoke --code 510300.SH` adds a live snapshot read to the default health,
tool discovery, and instrument-search checks.
