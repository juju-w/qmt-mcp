# Contract: MCP Tool Metadata, Results, and Profiles

## Listed tool

Every visible tool includes:

```json
{
  "name": "qmt_xtdata_snapshot",
  "title": "QMT Xtdata Snapshot",
  "description": "...",
  "inputSchema": {"type": "object"},
  "outputSchema": {
    "type": "object",
    "properties": {
      "ok": {"type": "boolean"},
      "error_type": {"type": ["string", "null"]},
      "error": {"type": ["string", "null"]},
      "details": {"type": ["object", "null"]}
    },
    "required": ["ok"],
    "additionalProperties": true
  },
  "annotations": {
    "readOnlyHint": true,
    "destructiveHint": false,
    "idempotentHint": true,
    "openWorldHint": true
  }
}
```

Exact optional-field schema encoding may use JSON Schema `anyOf` for nullability.
All four annotations are present even when a hint is not meaningful for a
read-only tool.

## Successful result

```json
{
  "resultType": "complete",
  "content": [
    {
      "type": "text",
      "text": "{\"ok\":true,\"data\":[]}"
    }
  ],
  "structuredContent": {
    "ok": true,
    "data": []
  },
  "isError": false
}
```

## Tool execution error

```json
{
  "resultType": "complete",
  "content": [
    {
      "type": "text",
      "text": "{\"ok\":false,\"error_type\":\"not_ready\",\"error\":\"QMT login required\",\"details\":{}}"
    }
  ],
  "structuredContent": {
    "ok": false,
    "error_type": "not_ready",
    "error": "QMT login required",
    "details": {}
  },
  "isError": true
}
```

The parsed text JSON and `structuredContent` are equal.

## Profile matrix

| Profile | Visible families |
|---|---|
| `full` | every otherwise enabled tool |
| `readonly` | tools annotated read-only |
| `market` | `core`, `xtdata` |
| `account` | `core`, `xttrade_query`, `portfolio` |
| `core` | `core` |
| `custom` | `core` plus allowlist matches |

Policy order:

1. Core tools are always visible.
2. The named profile selects candidate tools.
3. A non-empty allowlist further intersects candidates, except core.
4. The denylist removes matching non-core tools.

Patterns use shell-style matching such as `qmt_xtdata_option_*`.
