# Contract: QMT-MCP 1.0 Protocol Baseline

## Supported revision

```text
2026-07-28
```

No earlier MCP revision is supported by QMT-MCP 1.0.

## Accepted MCP request

Every POST to `/mcp` includes:

```http
MCP-Protocol-Version: 2026-07-28
Mcp-Method: <json-rpc method>
Mcp-Name: <tool/resource/task name when required>
```

The JSON-RPC params carry the modern metadata envelope:

```json
{
  "_meta": {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {
      "name": "example-client",
      "version": "1.0.0"
    },
    "io.modelcontextprotocol/clientCapabilities": {}
  }
}
```

The SDK validates routing-header and body agreement. Responses never contain
`Mcp-Session-Id`.

## Discovery

`server/discover` returns exactly one supported core revision:

```json
{
  "supportedVersions": ["2026-07-28"]
}
```

Capabilities may advertise independently versioned extensions such as Tasks
and, in later releases, MCP Apps.

## Unsupported protocol response

A missing or non-current `MCP-Protocol-Version` on POST `/mcp` returns HTTP 400
with JSON-RPC error `-32022`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32022,
    "message": "Unsupported MCP protocol version",
    "data": {
      "supported": ["2026-07-28"],
      "requested": "2025-11-25"
    }
  }
}
```

When the request id cannot be recovered safely, `id` is `null`. The rejection
contains no session header and does not dispatch a tool.

## Removed lifecycle and transport

QMT-MCP 1.0 does not support:

- `initialize` or `notifications/initialized`;
- `Mcp-Session-Id`;
- standalone GET streams or DELETE session termination;
- legacy HTTP+SSE transport configuration;
- qmtctl fallback to a 2025 initialize server.

Tasks `subscriptions/listen` may return a server-sent event stream as the direct
response to its modern POST. That is part of modern Streamable HTTP and is not
the removed legacy transport.
