# Contract: MCP Tasks Extension

## Capability negotiation

Stable MCP `2026-07-28` server capabilities include:

```json
{
  "extensions": {
    "io.modelcontextprotocol/tasks": {}
  }
}
```

A capable client declares the same extension. Supported 2025 sessions neither
advertise nor receive Tasks behavior.

## Start a task

An eligible `tools/call` is unchanged except for the declared extension. The
initial result is flat:

```json
{
  "resultType": "task",
  "taskId": "tsk_<unguessable>",
  "status": "working",
  "createdAt": "2026-07-31T12:00:00Z",
  "lastUpdatedAt": "2026-07-31T12:00:00Z",
  "ttlMs": 86400000,
  "pollIntervalMs": 1000
}
```

The record is committed before this response is emitted.

## `tasks/get`

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tasks/get",
  "params": {
    "taskId": "tsk_<id>"
  }
}
```

HTTP headers for Streamable HTTP include:

```text
Mcp-Method: tasks/get
Mcp-Name: tsk_<id>
```

A completed response nests the ordinary tool result:

```json
{
  "resultType": "complete",
  "taskId": "tsk_<id>",
  "status": "completed",
  "createdAt": "2026-07-31T12:00:00Z",
  "lastUpdatedAt": "2026-07-31T12:00:02Z",
  "ttlMs": 86400000,
  "pollIntervalMs": 1000,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "done"
      }
    ],
    "isError": false
  }
}
```

A failed response carries a JSON-RPC-shaped error under `error`. A cancelled
response carries no result. An input-required response carries
`inputRequests`; the complete interaction is specified in 024.

## `tasks/update`

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tasks/update",
  "params": {
    "taskId": "tsk_<id>",
    "inputResponses": {
      "confirmation": {
        "action": "accept"
      }
    }
  }
}
```

The response is a complete acknowledgement:

```json
{
  "resultType": "complete"
}
```

023 validates ownership, state, and response shape. Multi-round semantics are
completed in 024.

## `tasks/cancel`

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tasks/cancel",
  "params": {
    "taskId": "tsk_<id>"
  }
}
```

The response is `resultType: "complete"`. A following `tasks/get` reports
immutable `cancelled`.

## Errors

Unknown, malformed, expired, cross-principal, and insufficient-scope task
references all produce:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32602,
    "message": "Invalid task"
  }
}
```

A modern client invoking a task-required method without declaring the
extension receives the stable error:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32021,
    "message": "Missing required client capability",
    "data": {
      "requiredCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": {}
        }
      }
    }
  }
}
```

The unreleased ext-tasks draft code `-32003` is not emitted by this stable
implementation.

## qmtctl modes

- `wait`: advertise Tasks, poll using server guidance, and render the nested
  final tool result as the original command result.
- `detach`: advertise Tasks and return the initial task handle.
- `sync`: do not advertise Tasks; use direct `tools/call`.

Explicit `task` commands always declare Tasks and use the custom methods.
