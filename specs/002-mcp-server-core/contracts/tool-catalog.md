# Contract: MCP Tool Catalog And Capability Gating

**Feature**: 002-mcp-server-core

## Tool Family States

Each tool family has an observable state:

| State | Meaning |
|---|---|
| `enabled` | Tools are registered and callable. |
| `disabled` | Tools are intentionally not registered by config or feature scope. |
| `not_ready` | Tools are registered or discoverable but calls are refused until dependency readiness improves. |
| `not_authorized` | Runtime dependency reports missing broker/account permission. |
| `error` | Tool family failed initialization; see sanitized error code/message. |

For the current roadmap:

| Family | Default For 002 | Owner |
|---|---|---|
| `core` | `enabled` | 002 |
| `xtdata` | contract only; implemented in 003 | 003 |
| `xttrade_query` | `disabled`/`not_authorized` by default; enabled by 004 when explicitly configured and permissioned | 004 |
| `xttrade_write` | `disabled` | later guarded trading feature |

## Tool Contract Fields

Every registered tool must declare:

- `name`: stable MCP tool name.
- `family`: `core`, `xtdata`, `xttrade_query`, or future family.
- `description`: agent-facing behavior and limits.
- `input_schema`: explicit structured input model.
- `output_schema`: explicit structured output model.
- `readiness_requirement`: none, xtquant import, xtdata ready, trader connected, account authorized, etc.
- `capability_state`: how disabled/not-ready/not-authorized is reported.
- `audit_policy`: sanitized argument summary fields and account identifiers.
- `timeout_policy`: default timeout and whether the call is worker-backed.
- `error_types`: bounded set of client-visible error categories.

## Uniform Error Envelope

Tool failures return:

```json
{
  "ok": false,
  "error_type": "validation|not_ready|not_authorized|capacity|dependency|internal",
  "error": "short human-readable message",
  "details": {}
}
```

`details` must not include stack traces, tokens, full environment variables, or
raw credential-like values.

## Core Tools / Surfaces

The core may expose these non-business capabilities:

| Name | Purpose |
|---|---|
| `qmt_health` | MCP-visible health snapshot matching the HTTP health surface. |
| `qmt_capabilities` | Enabled/disabled tool-family states and reasons. |

Tool discovery remains the normal MCP mechanism for actual callable tools.
