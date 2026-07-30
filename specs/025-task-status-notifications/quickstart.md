# Quickstart: Task Status Notifications

## Protocol paths

```text
2026-07-28 + Tasks + taskIds -> notifications/tasks push
2026-07-28 + Tasks           -> tasks/get polling remains valid
2026-07-28 without Tasks     -> synchronous production tools
supported 2025 revisions     -> existing compatibility behavior
```

## Raw listen example

After creating a task, open a long-lived request:

```bash
curl -N \
  -H 'Authorization: Bearer <token>' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H 'Mcp-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: subscriptions/listen' \
  --data '{
    "jsonrpc":"2.0",
    "id":"task-listen-1",
    "method":"subscriptions/listen",
    "params":{
      "notifications":{"taskIds":["tsk_example"]},
      "_meta":{
        "io.modelcontextprotocol/protocolVersion":"2026-07-28",
        "io.modelcontextprotocol/clientInfo":{"name":"curl","version":"1"},
        "io.modelcontextprotocol/clientCapabilities":{
          "extensions":{"io.modelcontextprotocol/tasks":{}}
        }
      }
    }
  }' \
  https://qmt.example.com/mcp
```

Expect the subscription acknowledgement first, then one current
`notifications/tasks` snapshot and later changed snapshots.

## qmtctl

Default wait mode prefers notifications and falls back automatically:

```bash
qmtctl --url https://qmt.example.com/mcp \
  --task-mode wait \
  --task-timeout 10m \
  cache refresh --force
```

Existing alternatives remain:

```bash
qmtctl --task-mode detach cache refresh --force
qmtctl task get tsk_example
qmtctl task wait tsk_example
qmtctl --task-mode sync cache refresh --force
```

## Local acceptance

Run the Python and Go tiers:

```bash
cd appliance/mcp
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -m 'not integration'
.venv/bin/python -m pytest -m integration

cd ../../cli/qmtctl
go test ./...
go vet ./...
go build ./...
```

Run the official traceability scenario:

```bash
npx --yes '@modelcontextprotocol/conformance@0.2.0-alpha.10' server \
  --url http://127.0.0.1:8000/mcp \
  --scenario tasks-status-notifications \
  --force
```

The pinned harness currently reports this scenario as pending/skipped; the
project integration tier is the executable acceptance gate.
