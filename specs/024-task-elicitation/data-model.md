# Data Model: Task Elicitation

## Existing TaskRecord extension

024 reuses the 023 `TaskRecord`. Its `input_requests_json` field stores the
current `PendingInputSnapshot` only while status is `input_required`.

| Field | Type | Rules |
|---|---|---|
| `status` | enum | `working` or `input_required` while interaction is active |
| `input_requests_json` | nullable JSON object | Current unanswered requests only; maximum 16 and 64 KiB |
| `status_message` | nullable string | Safe prompt summary; never response content |
| `updated_at` | RFC 3339 timestamp | Changes on partial fulfillment and resume |

No response column is added.

## InputRequest

| Field | Type | Rules |
|---|---|---|
| `key` | string | Map key; 1-128 characters; unique for task lifetime |
| `method` | string | Standard MCP request method; 1-128 characters |
| `params` | JSON object | Method-specific bounded parameters |

Initial supported method:

```json
{
  "method": "elicitation/create",
  "params": {
    "mode": "form",
    "message": "Confirm deletion of safe.txt",
    "requestedSchema": {
      "type": "object",
      "properties": {
        "confirm": {"type": "boolean"}
      },
      "required": ["confirm"]
    }
  }
}
```

## InputResponse

For `elicitation/create`:

| Field | Type | Rules |
|---|---|---|
| `action` | enum | `accept`, `decline`, or `cancel` |
| `content` | optional JSON object | Present when accepted and required by the request |

The wire batch is keyed by the matching request key. It is validated, delivered
to the live waiter exactly once, and never persisted.

## TaskInteraction

| Field | Type | Rules |
|---|---|---|
| `task_id` | string | Existing durable task ID |
| `pending` | ordered map | Current request snapshot |
| `used_keys` | set | Every key used during this process lifetime |
| `responses` | map | Transient responses for the current round |
| `wake_event` | async event/future | Wakes only when all pending keys resolve or task terminates |
| `lock` | async lock | Serializes request, update, cancellation, and cleanup |
| `terminal` | boolean | Prevents late delivery after completion/cancellation |

The coordinator is removed when execution ends. Restart recovery fails active
records, so no coordinator reconstruction or response replay occurs.

## State transitions

```text
working
  -> input_required(requests A, B)
  -> input_required(request B)
  -> working
  -> input_required(request C)
  -> working
  -> completed | failed | cancelled
```

Rules:

- Request creation persists the full pending map before exposing it.
- Partial response replaces the durable snapshot but keeps
  `input_required`.
- Final response clears the snapshot and conditionally transitions to
  `working`.
- Cancellation/failure/completion makes the coordinator terminal and wakes
  waiters.
- A stale or duplicate update cannot move a terminal task.

## Bounds

- Maximum requests per round: 16.
- Maximum responses per update: 16.
- Maximum request key: 128 characters.
- Maximum method: 128 characters.
- Maximum compact request batch: 65,536 bytes.
- Maximum compact response batch: 65,536 bytes.
- Existing task and status-message bounds remain unchanged.
