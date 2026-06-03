# Quickstart: MCP Server Core

Goal: validate the MCP core without needing QMT login or xttrade permission.

## 1. Build / run the appliance

```bash
cd qmt-wine-rdp
docker compose up -d --build
```

## 2. Verify auth is enforced

```bash
curl -i http://<host>:<mcp_port>/healthz
# expect 401 unless explicitly running loopback-only dev mode

curl -sS -H "Authorization: Bearer $QMT_MCP_TOKEN" \
  http://<host>:<mcp_port>/healthz
```

Expected:

- `server` is `live` or `degraded`
- `broker_config` is visible
- `xtdata` and `xttrade` are separate states
- `xttrade` may be `not_authorized` without failing the core

## 3. Verify capabilities

Use an MCP client or a core tool call to inspect capabilities:

```text
qmt_capabilities
```

Expected:

- `core` is enabled
- `xtdata` is disabled until feature 003 is installed
- `xttrade_query` is disabled/not_authorized until broker permission exists
- no write/trade tools appear

## 4. Verify audit JSONL

```bash
docker exec <container> bash -lc 'tail -n 5 /broker/logs/mcp-audit.jsonl'
```

Expected:

- one JSON object per accepted call
- no bearer token or credential-like value

## 5. Verify responsiveness

Run a simulated slow worker-backed tool (added for the 002 smoke path), then call:

```bash
curl -sS -H "Authorization: Bearer $QMT_MCP_TOKEN" \
  http://<host>:<mcp_port>/healthz
```

Expected: health responds before the slow call finishes.
