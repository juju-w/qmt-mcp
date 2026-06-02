# Contract: broker.yaml (schema v1)

A pack's optional config file at `/broker/broker.yaml`. Every field is optional;
omitted fields are auto-detected. An invalid file fails the container fast.

```yaml
schema_version: 1            # REQUIRED if file present; MUST be 1

broker:
  id: <slug>                 # [a-z0-9-]+ ; default: pack dir name
  name: <display name>       # optional, free text

terminal:
  client: <relative/path.exe>   # optional; relative to /broker; must exist if set
  userdata: <relative/path>     # optional; userdata_mini dir; parent must be writable

xtquant:
  path: <relative/path>      # optional; the xtquant package dir (has __init__.py)
                             # or its parent; auto-detected if omitted

mcp:
  mode: readonly             # readonly (default) | trade  (trade deferred)
```

## Rules
- `schema_version` MUST equal `1`; any other value → fail fast.
- Unknown top-level keys are ignored with a warning (forward-compatible).
- `mcp.mode` MUST be `readonly` or `trade`; `trade` is accepted by the schema but
  enforcement/guardrails arrive in a later feature — in this feature `trade` does
  not enable any write tools.
- No secrets permitted in this file (Constitution VI).
- Relative paths are resolved against the pack mount (`/broker`).

## Minimal valid examples
Empty file (everything auto-detected) — valid.

```yaml
schema_version: 1
broker: { id: my-broker }
```
