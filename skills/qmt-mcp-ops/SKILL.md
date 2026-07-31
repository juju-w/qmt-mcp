---
name: qmt-mcp-ops
description: Deploy, operate, and troubleshoot the QMT-MCP appliance and qmtctl. Covers broker packs, static/OAuth/hybrid authorization, market subscriptions, account and portfolio queries, options, reference data, managed sectors, formula runtime, and CLI usage. Use for QMT MCP operations, client access, capability discovery, or appliance troubleshooting.
---

# QMT-MCP Operations

Operate the broker-neutral QMT appliance: Wine runs Windows QMT on native amd64,
and streamable HTTP MCP exposes xtdata plus gated account and analysis features.
The server and qmtctl prefer MCP `2026-07-28` and automatically retain the 2025
initialize/session path for older clients at the same `/mcp` URL.

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
  qmt_mcp_core/       auth, OAuth metadata, registry, health, audit, durable tasks
  qmt_mcp_xtdata/     market, search, subscriptions, options, reference, sectors, formulas
  qmt_mcp_xttrade/    read-only account queries
  qmt_mcp_portfolio/  read-only portfolio analytics
  qmt_mcp_db/         optional PostgreSQL persistence
cli/qmtctl/           compiled streamable HTTP client
specs/                feature specifications
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

In the default `rdp` display mode, RDP to `<host>:13389` and log into QMT after
every create or restart: the MCP server autostarts with that desktop session, so
until someone logs in there is no MCP. Set `QMT_DISPLAY_MODE=vnc` to have the MCP
start unattended (see below). The endpoint is `http://<host>:18765/mcp`; use TLS
for any non-local connection.

### Display modes (`QMT_DISPLAY_MODE`)

| Mode | MCP availability | Desktop |
|---|---|---|
| `rdp` (default) | Only after an RDP login starts the XFCE autostart | RDP `<host>:13389` |
| `vnc` | Unattended — `start-vnc.sh` owns Xvfb + x11vnc + QMT + the MCP supervisor under PID 1 | VNC `<host>:15900` |
| `both` | Unattended (same as `vnc`) | VNC + RDP |

`vnc` costs ~9 MB image and ~87 MB RAM, plus ~170 MB for `xfwm4` + `xfdesktop` +
`xfce4-panel`; `QMT_VNC_DESKTOP=0` serves a bare X root window instead (no window
decorations on QMT dialogs). The VNC desktop is always password-protected via
`QMT_VNC_PASSWORD`, defaulting to `QMT_RDP_PASSWORD`. Prefer `vnc` over `both`: an
RDP login creates a separate X session whose autostart spawns a second QMT
terminal.

Either mode still needs the **one-off interactive QMT account login** done by hand
on the desktop; that cannot be automated. Enable independent-trading / minimal
mode there if account queries are needed.

Run multiple brokers with one env file, project name, and port pair per
instance:

```bash
docker compose --env-file broker-a.env -p qmt-a up -d
docker compose --env-file broker-b.env -p qmt-b up -d
```

## Authentication

| Mode | Server responsibility | Client credential |
|---|---|---|
| `static` | Validate `QMT_MCP_TOKEN` | `QMT_MCP_TOKEN` / `--token` |
| `oauth` | Publish RFC 9728 metadata; verify external JWT through pinned JWKS; enforce scopes | qmtctl saved login or `QMT_MCP_ACCESS_TOKEN` |
| `hybrid` | Accept either path; static receives startup-visible admin surface | Either credential |

QMT-MCP is the resource server, never the authorization server. An external AS
owns login and token issuance. qmtctl can run Authorization Code + PKCE using a
Client ID Metadata Document (preferred), preregistered public client, or explicit
legacy DCR; it persists refresh rotation and provides status/logout. See
`docs/MCP-CLIENTS.md` for scope and Codex/Claude Code/WorkBuddy setup.

## Tool Profiles

Every listed tool has input/output schemas, standard behavior hints, exact
`structuredContent`, and an equivalent JSON text block. Select a startup-static
surface with `QMT_MCP_TOOL_PROFILE`:

| Profile | Surface |
|---|---|
| `full` | All otherwise enabled tools; default |
| `readonly` | Read-only tools only |
| `market` | Core and xtdata |
| `account` | Core, xttrade query, and portfolio |
| `core` | Core health and capabilities only |
| `custom` | Core plus `QMT_MCP_TOOL_ALLOWLIST` matches |

`QMT_MCP_TOOL_ALLOWLIST` and `QMT_MCP_TOOL_DENYLIST` are comma-separated shell
globs. Core tools cannot be hidden. Restart after changing the policy and inspect
`qmt_capabilities.tool_visibility` to confirm the effective counts.

OAuth scopes then intersect this startup surface:

| Scope | Access |
|---|---|
| `qmt:read` | required core |
| `qmt:market` | read-only xtdata |
| `qmt:account` | xttrade query and portfolio |
| `qmt:manage` | non-trading mutations in an already granted family |
| `qmt:admin` | all startup-visible tools |

Neither `qmt:manage` nor `qmt:admin` bypasses feature gates or enables trading.

## Catalog Pagination and Compression

The server applies Profile and OAuth visibility before paginating
`tools/list`. `QMT_MCP_LIST_PAGE_SIZE` defaults to 50; qmtctl follows all
opaque cursors automatically and rejects cycles or duplicate tools.
Tool-catalog pagination does not change business-level `limit` arguments.

MCP JSON responses at or above `QMT_MCP_GZIP_MIN_SIZE` use negotiated gzip
(default 1024 bytes). SSE is excluded. Set the threshold to `0` when an ingress
must own compression.

## Durable Tasks

Stable MCP `2026-07-28` clients that declare
`io.modelcontextprotocol/tasks` receive durable task handles for selected long
operations. Supported 2025 clients and modern non-declaring clients remain
synchronous on the same `/mcp` endpoint.

The default SQLite store is
`/broker/cache/mcp-tasks-v1.sqlite3`. It keeps lifecycle metadata, owner
digests, required scopes, and terminal output but excludes tool arguments,
credentials, and raw principal identifiers. Keep it on persistent real disk,
assign it to one active MCP server process, and include it in backups only if
detached task recovery matters. Startup marks interrupted active tasks failed;
terminal entries remain until TTL or bounded retention cleanup.

Production task-capable tools default to history download, batch history,
financial download, batch formula, factor generation, and instrument-cache
refresh. Configure them with `QMT_MCP_TASKS_ENABLED`,
`QMT_MCP_TASK_STORE`, `QMT_MCP_TASK_TTL_MS`,
`QMT_MCP_TASK_POLL_INTERVAL_MS`, `QMT_MCP_TASK_MAX_RETAINED`, and
`QMT_MCP_TASK_TOOLS`.

A task may pause with `status=input_required` and a keyed map of standard MCP
requests. Inspect the request `method` and `params`, then submit only deliberate
answers:

```bash
qmtctl --json task get tsk_<id>
qmtctl task update tsk_<id> \
  --responses-json \
  '{"confirmation":{"action":"accept","content":{"confirm":true}}}'
qmtctl task wait tsk_<id>
```

Partial batches leave unanswered keys pending. Never invent, infer, or
auto-accept a confirmation. Pending prompts are stored, but answer values stay
in the live task process and are not written to SQLite, logs, or audit records.
If the process restarts, waiting work fails explicitly instead of replaying
answers.

For stable clients, task status push uses
`subscriptions/listen.notifications.taskIds` and complete
`notifications/tasks` snapshots. The first frame confirms only authorized
owner/scope matches, followed by current state so reconnect does not require an
event log. Treat push as an optimization: polling remains valid, and qmtctl
automatically falls back after an unsupported, unacknowledged, malformed, or
lost stream. Both paths remain inside the same overall task timeout.

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

For an existing OAuth bearer:

```bash
export QMT_MCP_ACCESS_TOKEN=<access-token>
qmtctl auth discover --json
qmtctl health
```

`QMT_MCP_ACCESS_TOKEN` takes precedence over `QMT_MCP_TOKEN`. Equivalent global
flags are `--url`, `--access-token`/`--token`, `--json`, `--timeout`,
`--task-mode`, and `--task-timeout`.
The `tools` command always combines the complete paginated catalog and standard
Go HTTP gzip decoding is automatic.
Default task waiting prefers stable status notifications and falls back to
`tasks/get`; `--task-mode detach` and `--task-mode sync` keep their existing
semantics.

For browser login with persisted refresh:

```bash
qmtctl auth login \
  --client-id-metadata-url https://client.example.com/qmtctl.json \
  --scope 'qmt:read qmt:market'
qmtctl auth status
qmtctl auth logout
```

Explicit access/static tokens override the saved per-resource OAuth session.
Use `--auth-store` or `QMTCTL_AUTH_STORE` only when a non-default credential
store location is required.

| Command family | Typical use |
|---|---|
| `version`, `auth`, `health`, `tools`, `smoke` | Version, discovery, connectivity, registry |
| `task` | Get, wait, cancel, or update one durable task |
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
qmtctl --task-mode detach --json cache refresh --force
qmtctl task wait tsk_<id>
qmtctl --json task get tsk_<id>
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
| Exit code 21 / 22 | Invalid `QMT_DISPLAY_MODE`, or `vnc`/`both` with no VNC/RDP password set |
| Exit code 30-34 | VNC session failure; Xvfb, x11vnc, or the MCP supervisor died — see `~/.vnc/*.log` |
| `nodrv_CreateWindow` | Wine base drift or damaged prefix; use the pinned date tag |
| `/livez` is silent after restart | `rdp` mode: RDP session has not started MCP autostart; switch to `QMT_DISPLAY_MODE=vnc` for login-free startup |
| VNC desktop is black / QMT windows have no title bars | No window manager; keep `QMT_VNC_DESKTOP=1` so `xfwm4`+`xfdesktop`+`xfce4-panel` start |
| `audit sink is not writable` | Broker pack not owned by uid 1000; `chown -R 1000:1000 <pack>` |
| `xttrader.connect()==-1` | Broker has not enabled external/programmatic trading |
| `not_authorized` on account tools | Flag, account allowlist, or broker permission missing |
| OAuth discovery works but calls return 401 | Check JWT signature/`kid`, issuer, audience, expiry, client id, and algorithm |
| OAuth call returns 403 | Token lacks the family or `qmt:manage` scope named by the challenge |
| Long command prints a task handle | Detach mode is active; run `qmtctl task wait <id>` or use the default wait mode |
| `task_input_required` | Review `inputRequests`, submit an explicit keyed `task update`, then wait again; never auto-accept |
| Explicit task command says unsupported | Server/protocol did not advertise Tasks; use ordinary commands with `--task-mode sync` or upgrade the server |
| Task ID becomes invalid after OAuth change | Resume with the same principal and original tool scopes; unknown and unauthorized IDs intentionally share `-32602` |
| Chinese path decoding fails | Image or prefix is missing `zh_CN.GBK` |

## Security

- Keep bearer credentials only in gitignored environment files, qmtctl's
  permission-checked store, or a platform secret store.
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
