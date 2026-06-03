# Broker Packs

The appliance is split into a **broker-neutral base image** and a runtime-mounted
**broker pack**. Switch brokers by swapping the pack — never by rebuilding.

## What's in the base image (broker-neutral)
Wine new-WoW64, Windows Python 3.12, CJK fonts, `fastmcp`+`uvicorn`, the read-only
MCP launcher + scripts + XFCE autostart, xrdp, and `detect-broker`. **No** QMT
terminal, **no** xtquant, **no** account data.

## What's in a broker pack (mounted read-write at `/broker`)
```text
<pack>/
├── broker.yaml                 # optional (schema v1); see contract
├── bin.x64/XtItClient.exe      # the broker's extracted QMT terminal
├── userdata_mini/              # created/written at login
├── ... rest of the QMT tree ...
└── xtquant/                    # the MATCHING xtquant package (has __init__.py)
```
The pack is mounted **read-write** (QMT writes userdata/logs/config in-tree).
xtquant is **always** supplied by the pack (the base ships none) so its version
matches the terminal.

## `broker.yaml` (schema v1)
All fields optional; omitted → auto-detected. Full contract:
`specs/001-broker-pack-base/contracts/broker.yaml.schema.md`.
```yaml
schema_version: 1
broker: { id: my-broker, name: 我的券商 QMT }
terminal: { client: bin.x64/XtItClient.exe, userdata: userdata_mini }
xtquant:  { path: xtquant }
mcp:      { mode: readonly }   # readonly (default) | trade (deferred)
```

## Build a pack
```bash
scripts/make-broker-pack.sh <setup_qmt.exe> <xtquant_xxxxxx.rar> brokers/<id>/pack
```
Extracts the NSIS terminal (`7z`) and the RAR5 xtquant (`unrar`) and drops a
starter `broker.yaml`.

## Run / switch / multi-instance
```bash
# .env: QMT_MCP_TOKEN, INSTANCE, RDP_PORT, MCP_PORT, BROKER_PACK
docker compose up -d                       # run
# switch broker: point BROKER_PACK at another pack, same image — no rebuild
docker compose down && docker compose up -d
# multiple brokers on one host: one .env per instance (distinct INSTANCE/ports/
# token/BROKER_PACK), then:
docker compose --env-file broker-a.env -p qmt-a up -d
docker compose --env-file broker-b.env -p qmt-b up -d
```

## Startup resolution & fail-fast
`detect-broker` resolves client / userdata / xtquant (explicit `broker.yaml` wins;
otherwise auto-detect) and writes `/run/qmt/broker.env`. It **fails fast** (the
container exits, nothing left listening) when:

| Exit | Cause |
|---|---|
| 10 | `/broker` empty / unreadable / not writable |
| 11 | `broker.yaml` malformed / unsupported `schema_version` / bad `mcp.mode` |
| 12 | an explicit path in `broker.yaml` does not exist |
| 13 | client unresolved (0 or >1 candidates — set `terminal.client`) |
| 14 | xtquant unresolved (0 or >1 — set `xtquant.path`) |

## Login & MCP
Log into the QMT terminal manually over RDP (`<host>:RDP_PORT`, user `wineuser`).
The MCP (`<host>:MCP_PORT/sse`, bearer `QMT_MCP_TOKEN`) starts with the desktop
session; its trader tools come live after login (read-only by default).

## Apple Silicon
Build/run only under emulation; QMT native services may hit the Rosetta AVX
assertion. Use a native amd64 host.
