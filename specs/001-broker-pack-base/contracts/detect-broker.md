# Contract: detect-broker

**Invocation**: `detect-broker` runs inside `qmt-entrypoint.sh` (as root, Linux
side) before `exec /usr/bin/entrypoint`. Implemented in Python 3 (linux), using
`python3-yaml`.

## Inputs
- `/broker` — the mounted broker pack (read-write).
- `/broker/broker.yaml` — optional config (schema v1, see data-model).
- Env (optional overrides): `BROKER_MOUNT` (default `/broker`).

## Behavior
1. Verify the mount exists, is non-empty, and is writable; else fail fast.
2. Load `broker.yaml` if present; validate `schema_version == 1` and `mcp.mode`
   ∈ {`readonly`,`trade`}; malformed → fail fast (no fallback to guessing).
3. Resolve **client**, **userdata**, **xtquant** per the auto-detection algorithm
   (research D4): explicit value wins and must exist; otherwise scan; ambiguity
   (>1) or absence (0, where required) → fail fast with a specific message.
4. Convert resolved Linux paths to Wine paths with `winepath -w` (run as the
   target user).
5. Write `/run/qmt/broker.env` with the resolved keys (data-model), no secrets,
   and log a human-readable resolution summary to stderr.

## Outputs
- File `/run/qmt/broker.env` (KEY=VALUE), consumed downstream.
- Exit code `0` on success; non-zero on any fail-fast condition.

## Exit codes
| Code | Meaning |
|---|---|
| 0 | resolved; env written |
| 10 | mount empty/unreadable/not writable |
| 11 | broker.yaml malformed / unsupported schema_version / bad mcp.mode |
| 12 | configured (explicit) path missing |
| 13 | client unresolved (0 or >1 candidates) |
| 14 | xtquant unresolved (0 or >1 candidates) |

## Guarantees
- Fail closed: never starts RDP/MCP/QMT with an unresolved or ambiguous config.
- Idempotent: re-running with the same pack yields the same resolved env.
- Secret-free: logs and `broker.env` contain no credentials.
