# Contract: Task Status Notifications

## Capability

The server and capable client declare:

```json
{
  "extensions": {
    "io.modelcontextprotocol/tasks": {}
  }
}
```

Task notifications exist only on stable MCP `2026-07-28`.

## Listen Request

```json
{
  "jsonrpc": "2.0",
  "id": "task-listen-1",
  "method": "subscriptions/listen",
  "params": {
    "notifications": {
      "taskIds": [
        "tsk_example"
      ]
    },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientInfo": {
        "name": "example-client",
        "version": "1.0.0"
      },
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": {}
        }
      }
    }
  }
}
```

Streamable HTTP headers include:

```text
Accept: application/json, text/event-stream
Content-Type: application/json
Mcp-Protocol-Version: 2026-07-28
Mcp-Method: subscriptions/listen
```

## First Frame

The acknowledgement is always first:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/subscriptions/acknowledged",
  "params": {
    "notifications": {
      "taskIds": [
        "tsk_example"
      ]
    },
    "_meta": {
      "io.modelcontextprotocol/subscriptionId": "task-listen-1"
    }
  }
}
```

Unknown, expired, cross-principal, and insufficient-scope IDs are omitted from
`taskIds`. If none are accepted, the list is omitted and the stream may close.

## Current and Changed State

After acknowledgement, every accepted task receives a current snapshot. Later
durable transitions use the same shape:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tasks",
  "params": {
    "taskId": "tsk_example",
    "status": "completed",
    "createdAt": "2026-07-31T12:00:00.000Z",
    "lastUpdatedAt": "2026-07-31T12:00:02.000Z",
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
    },
    "_meta": {
      "io.modelcontextprotocol/subscriptionId": "task-listen-1"
    }
  }
}
```

The params match `tasks/get` except that notification params do not carry the
response discriminator `resultType`.

## Mixed Standard Filters

One request may combine Tasks with core subscriptions:

```json
{
  "notifications": {
    "toolsListChanged": true,
    "resourceSubscriptions": ["qmt://status"],
    "taskIds": ["tsk_example"]
  }
}
```

The acknowledgement and delivery preserve each accepted filter. Task streams
must never carry `notifications/progress` or `notifications/message`.

## Errors

Malformed or over-limit `taskIds` returns Invalid Params (`-32602`).

A client requesting `taskIds` without declaring the Tasks extension receives
Missing Required Client Capability (`-32021`).

The server never emits `notifications/tasks/status`.

## Reconnect and Fallback

There is no replay cursor. After any abrupt close, the client reopens
`subscriptions/listen`; the server sends current snapshots again. A client may
always use `tasks/get` instead, and qmtctl automatically does so if push
delivery cannot continue.
