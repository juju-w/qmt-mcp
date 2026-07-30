# Contract: Task Elicitation

## Negotiation

Complete task elicitation is available when:

```text
protocolVersion == 2026-07-28
client capabilities.extensions includes io.modelcontextprotocol/tasks
```

Supported 2025 clients and modern non-declaring clients continue the direct
synchronous path.

## Pause with input requests

`tasks/get` returns a point-in-time snapshot:

```json
{
  "resultType": "complete",
  "taskId": "tsk_<id>",
  "status": "input_required",
  "createdAt": "2026-07-31T12:00:00Z",
  "lastUpdatedAt": "2026-07-31T12:00:01Z",
  "ttlMs": 86400000,
  "pollIntervalMs": 1000,
  "statusMessage": "Waiting for confirmation",
  "inputRequests": {
    "confirmation": {
      "method": "elicitation/create",
      "params": {
        "mode": "form",
        "message": "Confirm deletion of safe.txt",
        "requestedSchema": {
          "type": "object",
          "properties": {
            "confirm": {"type": "boolean"}
          },
          "required": ["confirm"]
        }
      }
    }
  }
}
```

## Submit responses

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tasks/update",
  "params": {
    "taskId": "tsk_<id>",
    "inputResponses": {
      "confirmation": {
        "action": "accept",
        "content": {
          "confirm": true
        }
      }
    }
  }
}
```

HTTP routing headers remain:

```text
Mcp-Method: tasks/update
Mcp-Name: tsk_<id>
```

The acknowledgement contains no task snapshot:

```json
{
  "resultType": "complete"
}
```

After a partial batch, `tasks/get` contains only unanswered requests. After the
final answer it reports `working` or a terminal state, depending on how quickly
execution completes.

Unknown, already-satisfied, duplicate, and terminal-task keys are ignored after
task authorization. Unknown, expired, malformed, cross-principal, or
insufficient-scope task IDs still produce the indistinguishable 023
`-32602 Invalid task` response.

## MRTR-to-Tasks composition

Initial call:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "test_tool_with_task",
    "arguments": {}
  }
}
```

Initial result, before any task exists:

```json
{
  "resultType": "input_required",
  "inputRequests": {
    "user_name": {
      "method": "elicitation/create",
      "params": {
        "mode": "form",
        "message": "What is your name?",
        "requestedSchema": {
          "type": "object",
          "properties": {
            "name": {"type": "string"}
          },
          "required": ["name"]
        }
      }
    }
  }
}
```

The client retries the same call and adds:

```json
{
  "inputResponses": {
    "user_name": {
      "action": "accept",
      "content": {
        "name": "Alice"
      }
    }
  }
}
```

The server validates and resolves the retry before creating durable state.
Unknown or malformed responses return another `input_required` result or
Invalid Params without inserting a task. A resolved retry returns the ordinary
flat `resultType: "task"` handle in completed state. It does not carry
`requestState` or `inputRequests`; the nested tool result contains `Alice`.

## qmtctl

Inspect and answer explicitly:

```bash
qmtctl --json task get tsk_<id>
qmtctl task update tsk_<id> \
  --responses-json '{"confirmation":{"action":"accept","content":{"confirm":true}}}'
qmtctl task wait tsk_<id>
```

Neither default wait mode nor `task wait` fabricates or auto-accepts a response.
