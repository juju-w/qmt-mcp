# Data Model: Production MCP Server Core

## ResolvedBrokerConfig

| Field | Type | Notes |
|---|---|---|
| `broker_id` | string | From feature 001; safe for logs. |
| `broker_name` | string? | Optional display name. |
| `xtquant_dir_win` | string | Wine path to pack-provided xtquant. |
| `userdata_win` | string | Wine path to `userdata_mini`. |
| `mcp_mode` | enum `readonly`/`trade` | `trade` accepted as future flag, not enabling write tools in 002. |
| `source_file` | string | Resolved env/config source for diagnosis. |

Validation:

- Missing config produces `broker_config:error` and disables QMT-dependent tool
  families.
- Paths are consumed from 001; 002 does not re-detect broker packs.

## ToolFamilyCapability

| Field | Type | Notes |
|---|---|---|
| `family` | enum | `core`, `xtdata`, `xttrade_query`, `xttrade_write`, future values. |
| `state` | enum | `enabled`, `disabled`, `not_ready`, `not_authorized`, `error`. |
| `reason` | string | Short sanitized explanation. |
| `tools` | list[string] | Registered tool names, empty if disabled. |
| `updated_at` | timestamp | Last state transition. |

## ToolContract

| Field | Type | Notes |
|---|---|---|
| `name` | string | Stable MCP name. |
| `family` | enum | Tool family. |
| `description` | string | Agent-facing docstring. |
| `input_schema` | schema | Structured input model. |
| `output_schema` | schema | Structured output model. |
| `readiness_requirement` | enum | `none`, `xtquant_import`, `xtdata_ready`, `trader_connected`, etc. |
| `timeout_ms` | integer | Default max runtime. |
| `worker_backed` | bool | True for blocking QMT/xtquant calls. |
| `audit_fields` | list[string] | Sanitized fields to summarize. |
| `error_types` | list[enum] | Allowed client-visible error categories. |

## HealthState

| Field | Type | Notes |
|---|---|---|
| `ok` | bool | True when core service is live and required sinks are usable. |
| `server` | enum | `live`, `degraded`, `error`. |
| `broker_config` | enum | `loaded`, `missing`, `error`. |
| `xtquant_import` | enum | `unknown`, `ok`, `error`. |
| `xtdata` | enum | `disabled`, `not_ready`, `ready`, `error`. |
| `xttrade` | enum | `disabled`, `not_authorized`, `not_ready`, `connected`, `error`. |
| `audit` | enum | `ok`, `degraded`, `error`. |
| `tool_families` | list[ToolFamilyCapability] | Current family states. |

## AuditRecord

| Field | Type | Notes |
|---|---|---|
| `ts` | timestamp | ISO-8601 with timezone. |
| `request_id` | string | Generated per accepted call. |
| `broker_id` | string | Safe broker identifier. |
| `tool` | string | Tool name or surface name. |
| `family` | string | Tool family. |
| `account_id` | string? | Only for account tools; never required for xtdata. |
| `args_summary` | object | Sanitized bounded summary. |
| `outcome` | enum | `ok`, `error`, `refused`. |
| `error_type` | string? | Uniform error category. |
| `latency_ms` | integer | End-to-end tool latency. |

Default sink:

- JSONL append-only file.
- One JSON object per line.
- Postgres/database sinks are future optional adapters.

## ErrorEnvelope

```json
{
  "ok": false,
  "error_type": "validation",
  "error": "short message",
  "details": {}
}
```

Allowed `error_type` values for 002:

- `validation`
- `auth`
- `not_ready`
- `not_authorized`
- `disabled`
- `capacity`
- `dependency`
- `persistence`
- `internal`
