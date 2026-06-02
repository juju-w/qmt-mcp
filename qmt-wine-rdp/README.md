# qmt-wine-rdp

Self-contained QMT/MiniQMT image on Wine, based on
[`scottyhardy/docker-wine`](https://github.com/scottyhardy/docker-wine), served over RDP.

Unlike the earlier PoC (which left Python/xtquant/QMT as manual steps inside a
running container), this version **bakes the whole stack into the image at build
time** on a native `linux/amd64` host:

- `linux/amd64` runtime; new WoW64 Wine prefix via `WINEARCH=wow64`
- CJK fonts on the Linux desktop **and** inside the Wine prefix
- Windows Python 3.12 installed into the Wine prefix
- xtquant (`xtquant_250807`) placed into `site-packages`
- 金阳光/QMT (`setup_qmt.exe`, NSIS) extracted to `/workspace/QMT/extracted`
- reserved `8765` port for a future read-only QMT gateway

All three artifacts are **downloaded at build time** from their upstream URLs
(`--build-arg` to override), so the build context stays a few KB.

## Build (must run on a native amd64 host — the x86 NAS)

```bash
docker compose build          # downloads ~450 MB, installs Python+xtquant under Wine
docker compose up -d
```

> Apple Silicon: build/run only under emulation, where QMT's native quote/model
> services can hit the Rosetta AVX assertion
> (`ThreadContextSignals.cpp:414 rt_sigreturn`). Use the x86 NAS instead.

Ports (host → container):

```text
13389 → 3389   RDP
18765 → 8765   reserved gateway
```

## Connect

Use a real RDP client (macOS: **Windows App** / Microsoft Remote Desktop —
*not* VNC / Screen Sharing, which fail xrdp's X.224 handshake):

```text
host: <nas-ip>:13389
user: wineuser
pass: qmt
```

## Verify the baked stack

Inside the RDP desktop terminal (or `docker exec -u wineuser`):

```bash
verify-xtquant.sh        # prints Python version + confirms xtquant imports
```

## Launch QMT

```bash
start-qmt.sh             # runs /workspace/QMT/extracted/bin.x64/XtItClient.exe
```

1. Log into MiniQMT in minimal mode.
2. Confirm `userdata_mini` is generated.
3. xtquant lives in the same Wine prefix, so `xtdata` reads and
   `XtQuantTrader(path, session_id).connect()` work against it.

MiniQMT and xtquant must stay in the **same Wine prefix**. Do not share a macOS
Wine prefix with the Linux container.

## Persistence

The image is fully baked, so it starts with no volume. To persist the QMT login
/ `userdata_mini` and the Wine prefix across container recreation, uncomment the
`wine-home` volume in `docker-compose.yml`. Seed it from an **empty** volume so
the image content propagates; reusing an old volume masks the baked prefix.

## Customising versions

```bash
docker compose build \
  --build-arg PY_VERSION=3.12.10 \
  --build-arg XTQUANT_URL=https://dict.thinktrader.net/packages/xtquant_250807.rar \
  --build-arg QMT_SETUP_URL=https://downloadspeed.ebscn.com/zyrj/qmt/setup_qmt.exe
```

If you bump Python off 3.12, also update `PY_WIN_DIR` (`C:\PythonXY`) in the
`Dockerfile` to match.

## Non-goals

- noVNC/browser desktop
- high-performance remote desktop
- live trading endpoints
- running MiniQMT outside the container while xtquant runs inside
- exposing trading privileges directly to agents
