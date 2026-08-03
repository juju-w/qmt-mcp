# Data Model: Native Windows Launcher

## LauncherProfile

| Field | Type | Rules |
|---|---|---|
| `schemaVersion` | integer | `1` |
| `id` | string | Stable lowercase slug/UUID; no account identifier |
| `displayName` | string | User-facing broker/profile label |
| `clientPath` | string | Absolute existing Windows executable path |
| `workingDirectory` | string | Absolute directory containing the client |
| `xtquantRoot` | string | Absolute directory whose child is `xtquant` |
| `userdataPath` | string | Absolute `userdata_mini` or explicitly selected userdata |
| `mcpHost` | string | Must be `127.0.0.1` in schema version 1 |
| `mcpPort` | integer | 1024-65535; unique among saved profiles |
| `tokenSecretId` | string | Lookup key only; no plaintext/ciphertext in profile JSON |
| `autoStartLauncher` | boolean | Default false; current-user logon only |
| `restartTerminal` | boolean | Default false |
| `createdAt` | timestamp | UTC ISO-8601 |
| `updatedAt` | timestamp | UTC ISO-8601 |

## ResolvedBroker

An immutable validated result used to build child processes.

| Field | Source |
|---|---|
| `clientPath` | Explicit selection or chosen candidate |
| `workingDirectory` | Explicit override or client parent directory |
| `qmtRoot` | Parent of known `bin.x64` layout or bounded ancestor |
| `xtquantRoot` | Explicit override or unique detected import root |
| `userdataPath` | Explicit override, `userdata_mini`, or accepted `userdata` |
| `evidence` | Non-secret list of resolution decisions |

Validation is all-or-nothing. A missing client, missing xtquant package,
ambiguous import root, relative path, or unsupported host bind produces no
resolved result.

## SecretRecord

| Field | Type | Rules |
|---|---|---|
| `id` | string | Random lookup ID referenced by profile |
| `purpose` | enum | `mcpBearerToken` |
| `protectedValue` | bytes | Current-user DPAPI ciphertext on Windows |
| `createdAt` | timestamp | UTC |

Secret plaintext exists only during generation, process environment creation,
and deliberate clipboard copy. It is never serialized with profile data.

## LauncherSnapshot

| Field | Type | Values / meaning |
|---|---|---|
| `state` | enum | `stopped`, `validating`, `startingMcp`, `startingTerminal`, `waitingForLogin`, `ready`, `degraded`, `faulted`, `stopping` |
| `profileId` | string? | Active profile |
| `terminalOwnership` | enum | `none`, `attached`, `launched` |
| `terminalPid` | integer? | Ephemeral; never persisted |
| `mcpPid` | integer? | Ephemeral; never persisted |
| `mcpLive` | boolean | `/livez` result |
| `xtdataState` | string | Normalized health family state |
| `xttradeState` | string | Normalized optional family state |
| `summary` | string | Secret-free user-facing status |
| `lastError` | ErrorRecord? | Bounded actionable failure |
| `updatedAt` | timestamp | UTC |

## ErrorRecord

| Field | Type | Rules |
|---|---|---|
| `code` | string | Stable launcher error code |
| `component` | enum | `profile`, `terminal`, `mcp`, `health`, `secret`, `package` |
| `message` | string | User-facing and secret-free |
| `detail` | string? | Bounded diagnostic text after redaction |
| `retryable` | boolean | Controls Retry affordance |
| `occurredAt` | timestamp | UTC |

## State Transitions

```text
stopped -> validating -> startingMcp -> startingTerminal -> waitingForLogin
waitingForLogin -> ready
waitingForLogin -> degraded
ready -> degraded -> ready
startingMcp|startingTerminal|waitingForLogin|ready|degraded -> faulted
any active state -> stopping -> stopped
faulted -> validating (explicit retry)
```

An MCP crash may transition through `degraded` while bounded restart runs. A
terminal exit transitions to `degraded` unless terminal restart is explicitly
enabled and ownership is `launched`.
