# appliance

> Component-level build & ops reference. For the project overview, broker-pack
> model, and MCP usage, see the [root README](../README.md).

Self-contained QMT/MiniQMT image on Wine, based on
[`scottyhardy/docker-wine`](https://github.com/scottyhardy/docker-wine), served
over RDP with optional same-session VNC access.

The image is a **broker-neutral base**: it contains **NO** QMT terminal, **NO**
`xtquant`, and **NO** broker data. Those proprietary pieces are supplied at
runtime as a mounted **broker pack** (`/broker`). The image bakes only the
generic runtime, on a native `linux/amd64` host:

- `linux/amd64` runtime; new WoW64 Wine prefix via `WINEARCH=wow64`
- CJK fonts on the Linux desktop **and** inside the Wine prefix
- Windows Python 3.12 installed into the Wine prefix (downloaded at build time)
- official `mcp` Python SDK / `uvicorn` for the MCP server; `detect-broker` to resolve the pack
- source-built, checksum-pinned xrdp 0.10.6.1 + xorgxrdp 0.10.5 (TLS-only)
- opt-in x11vnc adapter for saved-credential and lightweight/mobile clients
- `8765` serves the read-only QMT **MCP** server (bearer-token; see root README)

Because nothing broker-specific is baked in, the build context stays tiny and the
**published image is safe to distribute** (`ghcr.io/<owner>/qmt-mcp`). Swap brokers
by pointing the mounted pack at another broker — no rebuild.

## Build (must run on a native amd64 host)

```bash
docker compose build          # downloads Windows Python, installs it + MCP under Wine
docker compose up -d          # mount a broker pack at /broker (see root README)
```

> Apple Silicon: build/run only under emulation, where QMT's native quote/model
> services can hit the Rosetta AVX assertion
> (`ThreadContextSignals.cpp:414 rt_sigreturn`). Use a native amd64 host instead.

Ports (host → container):

```text
127.0.0.1:13389 → 3389   RDP (loopback by default)
127.0.0.1:15900 → 5900   VNC (optional override, loopback by default)
18765 → 8765   MCP (bearer-token)
```

## MCP transport controls

The server paginates the authorized `tools/list` catalog with opaque cursors.
The default page size is 50; qmtctl consumes all pages automatically. This
transport-level pagination is separate from business `limit` arguments on
market-data tools.

Eligible JSON responses use negotiated gzip at 1024 bytes by default. SSE
remains uncompressed. Configure both in `.env`:

```env
QMT_MCP_LIST_PAGE_SIZE=50
QMT_MCP_GZIP_MIN_SIZE=1024
```

Set `QMT_MCP_GZIP_MIN_SIZE=0` if a reverse proxy should be the only compression
layer.

## Durable MCP Tasks

For stable MCP `2026-07-28` clients declaring
`io.modelcontextprotocol/tasks`, selected long-running tools return a durable
task handle. Supported 2025 clients and modern clients that do not declare the
extension retain synchronous `tools/call` behavior on the same endpoint.

Task state lives in the broker pack by default:

```env
QMT_MCP_TASKS_ENABLED=1
QMT_MCP_TASK_STORE=/broker/cache/mcp-tasks-v1.sqlite3
QMT_MCP_TASK_TTL_MS=86400000
QMT_MCP_TASK_POLL_INTERVAL_MS=1000
QMT_MCP_TASK_MAX_RETAINED=1000
```

The SQLite store excludes tool arguments, credentials, and raw principal
identifiers. It retains terminal results until TTL/bounded cleanup. A restart
marks interrupted work failed rather than leaving it permanently active.
Keep this file on persistent storage and do not share one store between
multiple concurrently running MCP server instances.

A task may pause as `input_required` with standard keyed MCP
`inputRequests`. `tasks/update` accepts partial answers and resumes after the
last pending key. Pending prompts are durable; response values remain
in-process and are never written to SQLite or logs. qmtctl exposes the task ID
and pending requests and requires an explicit `task update`; it does not
auto-confirm.

Stable clients may also request task IDs through
`subscriptions/listen.notifications.taskIds`. The acknowledgement is followed
by current and changed `notifications/tasks` snapshots. This is an optional
latency optimization: `tasks/get` remains the complete fallback for 2025,
polling-only, disconnected, and not-yet-upgraded clients. qmtctl selects this
path automatically and returns to server-guided polling if the stream cannot
continue.

## Desktop lifecycle

`QMT_DESKTOP_MODE=persistent` is the recommended default. Container startup
creates one Xorg/XFCE session and launches QMT plus MCP before an RDP client is
attached. Disconnecting and reconnecting returns to the same processes; it does
not create a second terminal. `manual` retains the old login-triggered behavior
as a rollback mode.

The desktop can start unattended, but the broker terminal may still present its
own login dialog. Until that login succeeds, `/livez` is available while
`qmt_health.xtdata` reports `degraded` or `awaiting_login`.

Optional VNC does not own another display. x11vnc attaches to this same
persistent Xorg session, so RDP and VNC observe one XFCE, QMT, and MCP process
tree. VNC is invalid in rollback-compatible `manual` mode.

## Connect

For RDP, use a real RDP client (macOS: **Windows App** / Microsoft Remote
Desktop; a VNC client cannot connect to the RDP port):

```text
host: 127.0.0.1:13389
user: wineuser
pass: <QMT_RDP_PASSWORD from .env>
```

The base Compose file binds RDP to loopback. From another machine, create a
tunnel first: `ssh -N -L 13389:127.0.0.1:13389 <user>@<nas>`.
There is no password default: use at least 12 random characters, preferably via
an owner-only mounted secret file. Direct LAN publication requires both a
non-loopback `RDP_BIND_ADDRESS` and `QMT_RDP_ALLOW_LAN=1`.

For a VNC client that can retain its credential, including lightweight Android
clients, enable the explicit override:

```bash
docker compose -f docker-compose.yml -f docker-compose.vnc.yml up -d
ssh -N -L 15900:127.0.0.1:15900 <user>@<nas>
```

Connect the VNC client to `127.0.0.1:15900`. Use a unique owner-only
`QMT_VNC_PASSWORD_FILE`; if no VNC secret is supplied, the resolved RDP password
is used. The password-file path must be supplied through a deployment-specific
Compose secret or read-only bind; the base file does not mount arbitrary host
secrets. Classic VNC authentication uses only the first eight characters and raw
VNC is not transport-encrypted. Keep the host bind on loopback and use SSH/VPN;
public exposure is unsupported. File transfer, remote commands, and clipboard
are disabled by default.

## Verify the base stack

Inside either remote desktop (or `docker exec -u wineuser`):

```bash
verify-xtquant.sh        # prints Python version; xtquant is provided by the pack
```

## Provide a broker pack, then launch QMT

The terminal + matching `xtquant` come from the mounted broker pack at `/broker`
(build one with `scripts/make-broker-pack.sh`; see the root README and
`docs/BROKER-PACK.md`). `detect-broker` resolves the client path from the pack.

```bash
start-qmt.sh             # launches the broker's QMT client resolved from /broker
```

1. Log into MiniQMT in minimal mode.
2. Confirm `userdata_mini` is generated under the pack.
3. The pack's `xtquant` lives in the same Wine prefix, so `xtdata` reads (and,
   with broker permission, `xttrader`) work against it.

The QMT terminal and `xtquant` must stay in the **same Wine prefix**. Do not share
a macOS Wine prefix with the Linux container.

## Persistence

The broker pack is mounted read-write at `/broker`, so the QMT login /
`userdata_mini` persist in the pack across container recreation. Keep the pack on
**real disk** (never tmpfs) — see the root README.

The generated RDP certificate persists in the project-scoped
`qmt-rdp-certs` volume. The live desktop survives client disconnects, but a
container restart intentionally creates a fresh desktop session.

## Customising versions

```bash
docker compose build --build-arg PY_VERSION=3.12.10
```

If you bump Python off 3.12, also update `PY_WIN_DIR` (`C:\PythonXY`) in the
`Dockerfile` to match. (There are no broker/xtquant build args — those live in the
broker pack, not the image.)

## Non-goals

- noVNC/browser desktop (native raw VNC is optional)
- live trading endpoints
- running MiniQMT outside the container while xtquant runs inside
- exposing trading privileges directly to agents
