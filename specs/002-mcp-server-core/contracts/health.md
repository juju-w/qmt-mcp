# Contract: Health And Capabilities

## HTTP Surface

`GET /healthz`

Authentication:

- Same bearer-token policy as all externally reachable MCP/HTTP surfaces.
- Local unauthenticated development mode is allowed only when explicitly bound
  to loopback.

Response shape:

```json
{
  "ok": true,
  "server": "live",
  "transport": "streamable-http",
  "broker_config": "loaded",
  "xtquant_import": "ok",
  "xtdata": "not_ready",
  "xttrade": "not_authorized",
  "audit": "ok",
  "tool_families": [
    {
      "family": "core",
      "state": "enabled",
      "reason": "core tools available",
      "tools": ["qmt_health", "qmt_capabilities"],
      "updated_at": "2026-06-03T12:00:00+08:00"
    },
    {
      "family": "xtdata",
      "state": "disabled",
      "reason": "feature 003 not installed",
      "tools": [],
      "updated_at": "2026-06-03T12:00:00+08:00"
    },
    {
      "family": "xttrade_query",
      "state": "not_authorized",
      "reason": "broker/account permission not available",
      "tools": [],
      "updated_at": "2026-06-03T12:00:00+08:00"
    }
  ]
}
```

## MCP Core Tools

### `qmt_health`

Returns the same health payload as `/healthz`.

### `qmt_capabilities`

Returns `transport` and `tool_families`, useful when an agent wants to
understand why a family such as `xttrade_query` is disabled.

## State Semantics

- `server=live`: MCP core can serve authenticated requests.
- `server=degraded`: core is alive but an important dependency/sink is degraded.
- `ok=false`: orchestration should treat the core as unhealthy.
- `xtdata` and `xttrade` states are independent; xttrade failure MUST NOT imply
  xtdata failure.
