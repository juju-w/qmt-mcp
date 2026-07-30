# Contract: Dual-Era MCP Lifecycle

## Preferred modern revision

qmtctl and the server prefer:

```text
2026-07-28
```

Modern requests use `server/discover`, contain the reserved
`io.modelcontextprotocol/{protocolVersion,clientInfo,clientCapabilities}`
metadata on every request, include `MCP-Protocol-Version` and `Mcp-Method`
headers, and include `Mcp-Name` for name-bearing methods. They do not use
initialize or `Mcp-Session-Id`.

The server returns non-negative `ttlMs` and `cacheScope` on cacheable list
results.

## Supported legacy revisions

When modern discovery is unsupported, qmtctl and the server support:

```text
2025-11-25
2025-06-18
2025-03-26
```

Legacy requests use the initialize/session flow below.

## Initialize request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "qmtctl",
      "version": "<build version>"
    }
  }
}
```

The legacy initialize request has no `MCP-Protocol-Version` header because
negotiation has not completed. It may include authorization but must not include
a stale session id.

## Initialize response

The response must contain:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "serverInfo": {
      "name": "QMT MCP",
      "version": "<runtime version>"
    }
  }
}
```

Additional fields are allowed. qmtctl stores an optional `Mcp-Session-Id`
response header.

## Initialized notification

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

The notification must not contain an `id`. For Streamable HTTP the server
responds with HTTP 202 and no JSON-RPC response body.

The request includes:

```text
MCP-Protocol-Version: <negotiated version>
Mcp-Session-Id: <issued session id, when present>
```

## Subsequent requests

Every later MCP HTTP request includes the negotiated
`MCP-Protocol-Version`. It includes `Mcp-Session-Id` only when the server issued
one. Authorization behavior remains unchanged.

## Response transports

qmtctl accepts:

- `application/json` containing one JSON-RPC response.
- `text/event-stream` whose message event contains the JSON-RPC response.

## Conformance contract

Modern server:

```text
tools-list
caching
http-header-validation
```

Modern discovery and sessionlessness are additionally required by the
same-endpoint integration test. The runner's `server-stateless` aggregate is
not selected because it requires the application-specific production tool
`test_missing_capability`.

Legacy server:

```text
server-initialize
ping
tools-list
```

Modern client:

```text
tools_call
request-metadata
http-standard-headers
```

Legacy client:

```text
initialize
tools_call
```

The conformance package version is fixed in CI. No expected-failure baseline is
permitted for these selected scenarios.
