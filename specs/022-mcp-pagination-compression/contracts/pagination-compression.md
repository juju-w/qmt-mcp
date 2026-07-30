# Contract: Tool Pagination and HTTP Compression

## `tools/list` request

The first request omits `cursor`. A continuation request copies the server's
cursor exactly:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {
    "cursor": "<opaque server value>"
  }
}
```

Modern requests additionally carry the required 2026 `_meta` and HTTP headers.
Legacy requests use the negotiated session headers. The cursor contract is
otherwise identical.

## `tools/list` response

An intermediate page contains:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "resultType": "complete",
    "tools": [],
    "nextCursor": "<opaque non-empty value>",
    "ttlMs": 0,
    "cacheScope": "private"
  }
}
```

The final page omits `nextCursor`. Tools are ordered by name. The union of all
pages is exactly the request-visible startup-profile and OAuth-authorized
catalog.

The cursor is not a credential. Clients must treat it as opaque. A malformed,
stale, or different-view cursor produces:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "Invalid pagination cursor"
  }
}
```

The error does not echo the cursor, decoded payload, fingerprint, or hidden
tool names.

## HTTP gzip

For an eligible JSON response:

```text
Request:
Accept-Encoding: gzip

Response:
Content-Encoding: gzip
Vary: Accept-Encoding
Content-Type: application/json
```

Eligibility requires an uncompressed body at or above
`QMT_MCP_GZIP_MIN_SIZE`. The default is 1024 bytes; zero disables application
compression. `text/event-stream` is always excluded.

Compression changes only HTTP representation bytes. Decompression must yield
the same JSON-RPC document as the identity response.

## qmtctl aggregation

`qmtctl tools` follows each non-empty cursor emitted by QMT MCP, emits one
combined `tools` array, and fails with a protocol error on:

- a repeated cursor;
- more than 1000 pages;
- a duplicate tool name across pages.
