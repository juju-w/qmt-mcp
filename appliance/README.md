# appliance

> Component-level build & ops reference. For the project overview, broker-pack
> model, and MCP usage, see the [root README](../README.md).

Self-contained QMT/MiniQMT image on Wine, based on
[`scottyhardy/docker-wine`](https://github.com/scottyhardy/docker-wine), served over RDP.

The image is a **broker-neutral base**: it contains **NO** QMT terminal, **NO**
`xtquant`, and **NO** broker data. Those proprietary pieces are supplied at
runtime as a mounted **broker pack** (`/broker`). The image bakes only the
generic runtime, on a native `linux/amd64` host:

- `linux/amd64` runtime; new WoW64 Wine prefix via `WINEARCH=wow64`
- CJK fonts on the Linux desktop **and** inside the Wine prefix
- Windows Python 3.12 installed into the Wine prefix (downloaded at build time)
- official `mcp` Python SDK / `uvicorn` for the MCP server; `detect-broker` to resolve the pack
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
13389 → 3389   RDP
15900 → 5900   VNC   (only served when QMT_DISPLAY_MODE=vnc|both)
18765 → 8765   MCP (bearer-token)
```

## Display modes

`QMT_DISPLAY_MODE` picks the graphical stack. This matters because it decides
whether the MCP needs a human to log in first.

| Mode | MCP availability | Desktop access |
|---|---|---|
| `rdp` (default) | **Only after an RDP login** — the XFCE autostart launches QMT + MCP, so the container stays unhealthy until someone logs in | RDP |
| `vnc` | **Automatic** — `start-vnc.sh` runs Xvfb + x11vnc + QMT + the MCP supervisor as children of PID 1, so `up -d` / restarts come up healthy unattended | VNC |
| `both` | Automatic (same as `vnc`) | VNC + RDP |

`vnc` costs ~9 MB image size and ~87 MB RAM (Xvfb + x11vnc) over `rdp`, plus
~170 MB for the XFCE window manager, desktop and panel.

The VNC session runs `xfwm4` + `xfdesktop` + `xfce4-panel` (not the full
`xfce4-session`, which needs D-Bus and a login session). Without a window manager
the desktop is a bare black root window and QMT's windows get no title bars — set
`QMT_VNC_DESKTOP=0` only if you deliberately want that. D-Bus warnings in
`~/.vnc/*.log` ("Failed to connect to session manager", "Failed to get system
bus", `org.xfce.SessionManager` unknown) are expected and harmless.

> `both` caveat: an RDP login creates a *separate* X session whose autostart would
> launch a second QMT terminal. The MCP is protected by the supervisor's pidfile,
> the terminal is not — prefer `vnc` unless you specifically need the RDP path.

Either way, the **one-off interactive QMT account login** still has to be done by
hand on the desktop; it cannot be automated. After that the credentials live in
the pack's `userdata_mini/`.

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

## Connect

**RDP** (`rdp`/`both` modes) — use a real RDP client (macOS: **Windows App** /
Microsoft Remote Desktop — *not* VNC / Screen Sharing, which fail xrdp's X.224
handshake):

```text
host: <nas-ip>:13389
user: wineuser
pass: <QMT_RDP_PASSWORD from .env>   # the compose default `qmt` is dev-only
```

**VNC** (`vnc`/`both` modes) — any VNC client; the desktop is always
password-protected (`QMT_VNC_PASSWORD`, defaulting to `QMT_RDP_PASSWORD`):

```text
host: <nas-ip>:15900
pass: <QMT_VNC_PASSWORD or QMT_RDP_PASSWORD from .env>
```

## Verify the base stack

Inside the desktop terminal (or `docker exec -u wineuser`):

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

## Customising versions

```bash
docker compose build --build-arg PY_VERSION=3.12.10
```

If you bump Python off 3.12, also update `PY_WIN_DIR` (`C:\PythonXY`) in the
`Dockerfile` to match. (There are no broker/xtquant build args — those live in the
broker pack, not the image.)

## Non-goals

- noVNC / browser desktop (raw VNC via `QMT_DISPLAY_MODE=vnc` is supported; the
  websockify + web-UI stack pulls ~53 extra packages and is deliberately omitted)
- high-performance remote desktop
- live trading endpoints
- running MiniQMT outside the container while xtquant runs inside
- exposing trading privileges directly to agents
