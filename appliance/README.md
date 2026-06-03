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
- `fastmcp` / `uvicorn` for the MCP server; `detect-broker` to resolve the pack
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
18765 → 8765   MCP (bearer-token)
```

## Connect

Use a real RDP client (macOS: **Windows App** / Microsoft Remote Desktop —
*not* VNC / Screen Sharing, which fail xrdp's X.224 handshake):

```text
host: <nas-ip>:13389
user: wineuser
pass: <QMT_RDP_PASSWORD from .env>   # the compose default `qmt` is dev-only
```

## Verify the base stack

Inside the RDP desktop terminal (or `docker exec -u wineuser`):

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

- noVNC/browser desktop
- high-performance remote desktop
- live trading endpoints
- running MiniQMT outside the container while xtquant runs inside
- exposing trading privileges directly to agents
