# Quickstart: Base Image + Broker Pack

Goal: build the broker-neutral base image once, then run any broker by mounting a
pack — no rebuild to switch.

## 1. Build the base image (native amd64 host)
```bash
cd appliance
docker compose build          # base only: Wine + Python3.12 + fonts + MCP deps
                              # NO setup_qmt, NO xtquant baked in
```

## 2. Make a broker pack (once per broker environment)
```bash
# from the broker's installer + a matching xtquant rar
scripts/make-broker-pack.sh \
    /path/to/setup_qmt.exe \
    /path/to/xtquant_250807.rar \
    brokers/guangda-jinyangguang/pack
# -> extracts the terminal (7z) + xtquant (unrar) and drops a starter broker.yaml
```
Edit `brokers/guangda-jinyangguang/pack/broker.yaml` only if auto-detection needs
help (multiple client exes, non-standard layout).

## 3. Run
```bash
# .env holds QMT_MCP_TOKEN and the pack path + ports for this instance
docker compose up -d
```
`docker-compose.yml` mounts `brokers/<id>/pack` → `/broker` (read-write).

## 4. Verify (acceptance)
```bash
# detect-broker resolution in logs (no secrets)
docker logs <container> | grep -i 'broker resolved'

# RDP reachable
nc -z <host> <rdp_port>

# MCP up + token enforced
curl -s -o /dev/null -w '%{http_code}\n' http://<host>:<mcp_port>/sse            # 401
curl -s -H "Authorization: Bearer $QMT_MCP_TOKEN" http://<host>:<mcp_port>/sse   # 200 event-stream

# xtquant imports from the pack at runtime (Wine python)
docker exec -u wineuser <container> bash -lc 'verify-xtquant.sh'
```

## 5. Switch brokers (the whole point)
```bash
docker compose down
# point the pack mount at another broker's pack (edit .env / override), same image
docker compose up -d          # NO rebuild
```

## Fail-fast checks (expected non-zero, nothing left listening)
- empty `/broker` mount → exit 10
- pack with a client but no xtquant → exit 14
- two candidate client exes, no `terminal.client` → exit 13 (lists candidates)

## Apple Silicon note
Build/run only under emulation; QMT native services may hit the Rosetta AVX
assertion (`ThreadContextSignals.cpp:414`). Use a native amd64 host.
