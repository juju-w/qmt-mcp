# Quickstart: Tool Contracts and Profiles

## Local tests

```bash
cd appliance/mcp
ruff check .
ruff format --check .
pytest -m 'not integration'
pytest -m integration
```

## Start a bounded profile

```bash
PYTHONPATH=appliance/mcp \
MCP_HOST=127.0.0.1 \
MCP_PORT=18766 \
QMT_MCP_ALLOW_UNAUTH_LOOPBACK=1 \
QMT_MCP_ENABLE_XTDATA=0 \
QMT_MCP_TOOL_PROFILE=core \
QMT_MCP_AUDIT_PATH=/tmp/qmt-mcp-020-audit.jsonl \
python3.12 appliance/mcp/qmt_mcp.py
```

Expected visible tools:

```text
qmt_capabilities
qmt_health
```

## Custom market subset

```bash
QMT_MCP_TOOL_PROFILE=custom
QMT_MCP_TOOL_ALLOWLIST='qmt_xtdata_snapshot,qmt_xtdata_bars,qmt_xtdata_option_*'
```

Core tools remain visible automatically.
