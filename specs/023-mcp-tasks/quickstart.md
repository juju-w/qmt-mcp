# Quickstart: MCP Tasks

## Server defaults

Existing deployments require no client migration:

```bash
QMT_MCP_TASKS_ENABLED=1
QMT_MCP_TASK_STORE=/broker/cache/mcp-tasks-v1.sqlite3
QMT_MCP_TASK_TTL_MS=86400000
QMT_MCP_TASK_POLL_INTERVAL_MS=1000
QMT_MCP_TASK_MAX_RETAINED=1000
```

The server primarily advertises Tasks to MCP `2026-07-28` clients that can
declare the extension. Older and non-declaring clients continue synchronous
tool calls.

Disable task conversion while preserving every tool:

```bash
QMT_MCP_TASKS_ENABLED=0
```

## qmtctl

Wait for the final result, which is the default:

```bash
qmtctl --url https://qmt.example.com/mcp \
  cache refresh --force
```

Detach and retain the task ID:

```bash
qmtctl --task-mode detach \
  --json cache refresh --force
```

Resume, inspect, or cancel:

```bash
qmtctl task get tsk_<id>
qmtctl task wait tsk_<id>
qmtctl task cancel tsk_<id>
```

Force the compatibility path:

```bash
qmtctl --task-mode sync cache refresh --force
```

`--timeout` bounds one HTTP exchange. `--task-timeout` bounds the complete
wait lifecycle.

## Local verification

```bash
cd appliance/mcp
ruff check .
ruff format --check .
pytest -m 'not integration'
pytest -m integration

cd ../../cli/qmtctl
go test ./...
go vet ./...
go build ./...
```
