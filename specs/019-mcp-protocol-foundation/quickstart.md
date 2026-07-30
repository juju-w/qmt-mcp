# Quickstart: MCP Protocol Foundation

## Python checks

```bash
cd appliance/mcp
python3.12 -m pip install -r requirements.txt
ruff check .
ruff format --check .
pytest -m 'not integration'
pytest -m integration
```

## qmtctl checks

```bash
cd cli/qmtctl
go test ./...
go vet ./...
go build ./...
go build -o /tmp/qmtctl-conformance ./cmd/conformance
```

## Official server conformance

Start the broker-neutral test server:

```bash
PYTHONPATH=appliance/mcp \
MCP_HOST=127.0.0.1 \
MCP_PORT=18766 \
QMT_MCP_ALLOW_UNAUTH_LOOPBACK=1 \
QMT_MCP_ENABLE_XTDATA=0 \
QMT_MCP_AUDIT_PATH=/tmp/qmt-mcp-conformance-audit.jsonl \
python3.12 appliance/mcp/qmt_mcp.py
```

Then run:

```bash
for scenario in tools-list caching http-header-validation; do
  npx --yes @modelcontextprotocol/conformance@0.2.0-alpha.10 server \
    --url http://127.0.0.1:18766/mcp \
    --spec-version 2026-07-28 \
    --scenario "$scenario"
done

for scenario in server-initialize ping tools-list; do
  npx --yes @modelcontextprotocol/conformance@0.2.0-alpha.10 server \
    --url http://127.0.0.1:18766/mcp \
    --spec-version 2025-11-25 \
    --scenario "$scenario"
done
```

## Official qmtctl client conformance

```bash
for scenario in tools_call request-metadata http-standard-headers; do
  npx --yes @modelcontextprotocol/conformance@0.2.0-alpha.10 client \
    --command /tmp/qmtctl-conformance \
    --spec-version 2026-07-28 \
    --scenario "$scenario"
done

for scenario in initialize tools_call; do
  npx --yes @modelcontextprotocol/conformance@0.2.0-alpha.10 client \
    --command /tmp/qmtctl-conformance \
    --spec-version 2025-11-25 \
    --scenario "$scenario"
done
```
