# Data Model: Task Status Notifications

025 adds no durable table. It projects existing `TaskRecord` state into bounded
in-memory subscription entities.

## Task Subscription Filter

| Field | Type | Rules |
|---|---|---|
| `task_ids` | ordered tuple of string | Optional, deduplicated, at most 64 |
| core filters | SDK `SubscriptionFilter` | Preserved unchanged |

Requested IDs are untrusted. Accepted IDs are the ordered subset that exists,
belongs to the current principal, and remains authorized by current scopes.

## Task State Event

| Field | Type | Purpose |
|---|---|---|
| `task_id` | string | Fast subscription matching |
| `owner_digest` | 64-character digest | Defense-in-depth local routing only |
| `snapshot` | immutable JSON-compatible mapping | Exact client-visible state at commit |

The owner digest is never serialized. The snapshot excludes `resultType`,
tool name, required scopes, expiry epoch, arguments, and input responses.

## Listen Stream State

| Field | Type | Purpose |
|---|---|---|
| `subscription_id` | JSON-RPC request ID | Correlates every stream frame |
| `accepted_task_ids` | immutable set | Task delivery filter |
| `owner_digest` | digest | Prevents cross-principal delivery |
| `queue` | bounded event stream | Isolates publishers from network I/O |
| `core_filter` | SDK filter | Preserves tool/prompt/resource events |

Listener state is process-local and is deleted on disconnect, cancellation,
graceful close, or queue overflow.

## Task Status Notification

The notification params are the existing detailed task projection:

- identity and status;
- creation and last-update timestamps;
- TTL and polling guidance;
- optional status message;
- optional terminal result or error;
- optional pending input requests.

It adds `_meta.io.modelcontextprotocol/subscriptionId` and does not add a
`resultType`.

## State Flow

```text
TaskStore transition commits
        |
        v
immutable TaskStateEvent
        |
        v
shared subscription bus
        |
        +--> authorized matching stream queue
        |
        +--> other streams ignored
```

On initial listen, current snapshots come directly from `TaskStore` after the
listener is registered. This closes the snapshot-to-live-event race without a
replay log.
