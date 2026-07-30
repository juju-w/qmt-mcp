# qmtctl

`qmtctl` is the compiled command-line client for QMT-MCP. It uses the official
MCP Go SDK, prefers stable MCP `2026-07-28`, and automatically falls back to the
supported 2025 initialize/session flow. It never imports `xtquant` or duplicates
broker logic locally.

`qmtctl tools` follows every standard `tools/list` cursor and presents one
complete catalog. It also uses Go's standard transparent gzip negotiation and
decoding. There is no paging or compression flag, and single-page servers keep
the same output.

For stable `2026-07-28` servers, qmtctl declares MCP Tasks and waits for
selected long-running tools by default. Its normal human and JSON output remains
the final tool result.

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

## Long-running Tasks

Execution modes are available as `--task-mode` or `QMTCTL_TASK_MODE`:

| Mode | Behavior |
|---|---|
| `wait` | Default. Start a task, poll using server guidance, and print the final tool result. |
| `detach` | Return the task handle immediately so another process can resume it. |
| `sync` | Do not declare Tasks; request the server's synchronous compatibility path. |

```bash
qmtctl cache refresh --force
qmtctl --task-mode detach --json cache refresh --force
qmtctl task get tsk_<id>
qmtctl task wait tsk_<id>
qmtctl task cancel tsk_<id>
qmtctl task update tsk_<id> \
  --responses-json \
  '{"confirmation":{"action":"accept","content":{"confirm":true}}}'
```

Stable task input uses keyed standard MCP requests. If automatic wait reaches
`input_required`, qmtctl stops and returns a `task_input_required` error whose
data contains the task ID and pending `inputRequests`. Review those requests,
submit an explicit keyed response, then run `task wait` again. qmtctl never
auto-accepts a confirmation.

`--responses-json` must be a JSON object with at most 16 entries and 64 KiB.
Partial responses leave only unanswered keys pending. Unknown, duplicate,
already-satisfied, and terminal-task keys are acknowledged and ignored by the
server after authorization.

`--timeout` bounds each HTTP exchange. `--task-timeout`, or
`QMTCTL_TASK_TIMEOUT`, bounds the full wait lifecycle and defaults to 10
minutes. A detached task remains valid server-side after qmtctl exits. Explicit
`task` commands require a server advertising Tasks; ordinary commands still
work synchronously against older or non-Tasks servers.

## Commands

```bash
qmtctl version
qmtctl auth discover
qmtctl auth login --client-id qmtctl-public --scope 'qmt:read qmt:market'
qmtctl auth status
qmtctl auth logout
qmtctl health
qmtctl tools
qmtctl task get tsk_<id>
qmtctl task wait tsk_<id>
qmtctl task cancel tsk_<id>
qmtctl task update tsk_<id> --responses-json '<keyed-json-object>'
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
