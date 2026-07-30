# Data Model: MCP Tasks

## TaskRecord

| Field | Type | Rules |
|---|---|---|
| `task_id` | string | Primary key; `tsk_` plus cryptographic random token; bounded |
| `owner_digest` | string | SHA-256 digest of stable principal components |
| `tool_name` | string | Registered tool name; bounded |
| `required_scopes_json` | JSON array | Normalized original required scopes |
| `status` | enum | `working`, `input_required`, `completed`, `failed`, `cancelled` |
| `status_message` | nullable string | Safe bounded operator/client message |
| `created_at` | RFC 3339 timestamp | Immutable UTC creation time |
| `updated_at` | RFC 3339 timestamp | Monotonic lifecycle update time |
| `expires_at` | nullable timestamp | Creation plus TTL; null means unlimited |
| `ttl_ms` | nullable integer | Stable wire value |
| `poll_interval_ms` | nullable integer | Minimum client polling guidance |
| `result_json` | nullable JSON | Ordinary terminal MCP tool result |
| `error_json` | nullable JSON | Terminal JSON-RPC error |
| `input_requests_json` | nullable JSON | Current structured requests for 024 |

The model deliberately excludes tool arguments, authorization headers, access
tokens, refresh tokens, raw subjects, raw client IDs, and raw issuers.

## State transitions

```text
working -> input_required
working -> completed
working -> failed
working -> cancelled
input_required -> working
input_required -> completed
input_required -> failed
input_required -> cancelled
```

`completed`, `failed`, and `cancelled` are terminal and immutable. Concurrent
updates use conditional SQL transitions so exactly one terminal outcome wins.

## Persistence rules

- Insert and commit before returning the initial task handle.
- Use one schema version table and idempotent migration transaction.
- Set the SQLite file to owner read/write permissions where supported.
- Treat missing, malformed, unauthorized, and expired IDs identically at the
  protocol layer.
- Delete expired records during bounded cleanup.
- If terminal count exceeds `max_retained`, remove oldest terminal records.
- Never prune `working` or `input_required` because of count alone.
- On process startup, atomically convert stored non-terminal records to
  `failed` with MCP Internal Error (`-32603`) and an interruption message.

## Principal derivation

OAuth and hybrid modes derive:

```text
SHA-256(version || client_id || issuer || subject)
```

Length-prefixing or structured JSON prevents ambiguous concatenation. Static
mode hashes a deployment-local constant marker. Only the digest is persisted.

## Indexes

- Primary key on `task_id`.
- Index on `(status, updated_at)` for cleanup and restart recovery.
- Index on `expires_at` for expiry cleanup.

No principal listing method is exposed, so an owner index is not required by
the protocol.
