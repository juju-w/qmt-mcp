# Broker Pack contract

A **broker pack** is everything broker-specific, kept *outside* the image so you
can switch QMT environments by swapping a mounted directory — the base image is
identical for every broker.

## What a broker pack contains

```
<broker-pack>/                 # mounted at /broker (read-only is fine)
├── bin.x64/XtItClient.exe     # the broker's QMT/MiniQMT client (the "exe to swap")
├── userdata_mini/             # created/populated by the client after login
├── xtquant/                   # the xtquant python package matching this build
└── broker.yaml                # the contract file (see brokers/template/broker.yaml)
```

Only `broker.yaml` is authored by you; the rest is the broker's extracted QMT
install (from their `setup_qmt.exe`, 7z-extracted) plus the matching `xtquant`.

## How the base image consumes it

On container start the entrypoint:

1. Reads `/broker/broker.yaml` (all fields optional).
2. **Auto-detects** anything omitted by scanning `/broker`:
   - client exe — first match among known client names,
   - `userdata_mini` — first dir of that name,
   - `xtquant` — first `xtquant/` package dir.
3. Resolves Wine paths (`Z:\broker\...`), exports them, fails fast with a clear
   message if the client exe or xtquant can't be found.
4. Puts the pack's `xtquant` on the Wine Python path when `xtquant.source: pack`.
5. Starts xrdp; on RDP/XFCE login the client + MCP auto-start.

## Switching brokers

```bash
# point the volume at a different broker's extracted QMT + its broker.yaml
BROKER_PACK=/srv/brokers/haitong  docker compose up -d
```

No rebuild. Run several brokers at once by giving each its own pack, port and
`QMT_MCP_TOKEN` (compose profiles / one service per broker).

## Making a new broker pack

1. Get the broker's QMT installer, 7z-extract it into `<pack>/` (so
   `<pack>/bin.x64/<client>.exe` exists).
2. Drop the matching `xtquant/` into `<pack>/xtquant`.
3. Copy `brokers/template/broker.yaml` to `<pack>/broker.yaml`; set `broker.id`,
   and only override `client_exe`/`userdata_mini` if auto-detect picks wrong.
4. `docker compose up -d` pointing `BROKER_PACK` at it. Connect via RDP, log in,
   confirm `/healthz` reports `xtdata`/`trader` connected.
