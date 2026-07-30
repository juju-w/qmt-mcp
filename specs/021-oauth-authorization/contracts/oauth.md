# Contract: OAuth Resource and Tool Scopes

## Protected Resource Metadata

Both standard paths return the same RFC 9728 document:

```json
{
  "resource": "https://qmt.example.com/mcp",
  "resource_name": "QMT MCP",
  "authorization_servers": ["https://auth.example.com"],
  "scopes_supported": [
    "qmt:read",
    "qmt:market",
    "qmt:account",
    "qmt:manage",
    "qmt:admin"
  ],
  "bearer_methods_supported": ["header"]
}
```

Paths:

```text
/.well-known/oauth-protected-resource
/.well-known/oauth-protected-resource/mcp
```

Responses include:

```text
Access-Control-Allow-Origin: *
Cache-Control: public, max-age=300
```

## Authentication Challenge

Missing or invalid token:

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer resource_metadata="https://qmt.example.com/.well-known/oauth-protected-resource/mcp", scope="qmt:read", resource="https://qmt.example.com/mcp"
```

Insufficient scope:

```http
HTTP/1.1 403 Forbidden
WWW-Authenticate: Bearer error="insufficient_scope", scope="qmt:market", resource_metadata="https://qmt.example.com/.well-known/oauth-protected-resource/mcp", resource="https://qmt.example.com/mcp"
```

Bodies use the existing JSON error envelope and never include token-validation
internals.

## Tool Scope Matrix

| Family / behavior | Required scopes |
|---|---|
| `core` | `qmt:read` |
| `xtdata`, read-only | `qmt:read qmt:market` |
| `xtdata`, mutation | `qmt:read qmt:market qmt:manage` |
| `xttrade_query`, read-only | `qmt:read qmt:account` |
| `portfolio`, read-only | `qmt:read qmt:account` |
| Any startup-visible tool with admin | `qmt:read qmt:admin` |

There are no trading families or trading scopes.

## JWT Claims

Required:

```json
{
  "iss": "https://auth.example.com",
  "aud": "https://qmt.example.com/mcp",
  "exp": 1780000000,
  "client_id": "agent-client",
  "scope": "qmt:read qmt:market"
}
```

`aud` may be an array. `azp` may substitute for `client_id`; `sub` is retained
as the optional resource-owner identity. `scp` as an array may substitute for
`scope`. Conflicting or malformed scope representations fail closed.
