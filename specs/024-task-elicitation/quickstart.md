# Quickstart: Task Elicitation

## Compatibility

The same deployment supports both lines:

```text
2026-07-28 + declared Tasks -> tasks and multi-round task input
2026-07-28 without Tasks    -> synchronous production tools
supported 2025 revisions   -> synchronous production tools
```

No new server setting is required beyond the 023 Tasks configuration.

## Inspect a waiting task

```bash
qmtctl --json task get tsk_<id>
```

The `inputRequests` object is keyed. Review its standard `method` and `params`
before supplying an answer.

## Answer explicitly

```bash
qmtctl task update tsk_<id> \
  --responses-json \
  '{"confirmation":{"action":"accept","content":{"confirm":true}}}'

qmtctl task wait tsk_<id>
```

For several prompts, answer a subset and inspect the remaining requests before
continuing:

```bash
qmtctl task update tsk_<id> \
  --responses-json '{"first":{"action":"accept","content":{"value":"one"}}}'
qmtctl --json task get tsk_<id>
```

qmtctl never auto-accepts a confirmation.

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
go build ./cmd/conformance
```

The CI conformance service additionally enables:

```bash
QMT_MCP_TASK_CONFORMANCE_FIXTURES=1
```

That flag is test-only and must not be enabled in production.
