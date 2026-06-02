# Phase 1 Data Model: Broker Pack

## Entity: broker.yaml (schema v1)

All fields optional; omitted fields are auto-detected.

| Field | Type | Default | Validation |
|---|---|---|---|
| `schema_version` | int | `1` | MUST be `1`; unknown → fail fast |
| `broker.id` | string | derived from dir | slug `[a-z0-9-]+`; used in logs/identification |
| `broker.name` | string | — | free text (display) |
| `terminal.client` | string (rel path) | auto-detect | if set, MUST exist under `/broker`, else fail |
| `terminal.userdata` | string (rel path) | auto-detect | if set, parent MUST be writable |
| `xtquant.path` | string (rel path) | auto-detect | if set, MUST contain `xtquant/__init__.py` |
| `mcp.mode` | enum `readonly`\|`trade` | `readonly` | `trade` deferred to a later feature; unknown → fail |

Example (`brokers/guangda-jinyangguang/broker.yaml`):
```yaml
schema_version: 1
broker:
  id: guangda-jinyangguang
  name: 光大证券 金阳光
terminal:
  client: bin.x64/XtItClient.exe   # optional; auto-detected if omitted
  userdata: userdata_mini          # optional
xtquant:
  path: xtquant                    # optional; dir or its parent
mcp:
  mode: readonly
```

## Entity: Broker Pack (on-disk layout)

A host directory mounted read-write at `/broker`:
```text
/broker/
├── broker.yaml                  # optional
├── bin.x64/XtItClient.exe       # the QMT terminal (extracted)
├── userdata_mini/               # created/written at login (writable)
├── ... (rest of the extracted QMT tree) ...
└── xtquant/                     # the matching xtquant package (has __init__.py)
```
- Mounted **read-write**; QMT persists state in-tree.
- One running instance owns one pack exclusively.

## Entity: Resolved Configuration (runtime, derived)

Produced by `detect-broker` into `/run/qmt/broker.env` (no secrets), Windows
paths via `winepath -w`:

| Key | Meaning | Example |
|---|---|---|
| `QMT_BROKER_ID` | resolved broker id | `guangda-jinyangguang` |
| `QMT_CLIENT_WIN` | client exe (Wine path) | `Z:\broker\bin.x64\XtItClient.exe` |
| `QMT_BIN_DIR_WIN` | client dir (Wine path) | `Z:\broker\bin.x64` |
| `QMT_USERDATA_WIN` | userdata_mini (Wine path) | `Z:\broker\userdata_mini` |
| `QMT_XTQUANT_DIR_WIN` | xtquant parent (Wine path, for sys.path) | `Z:\broker` |
| `QMT_MCP_MODE` | `readonly`\|`trade` | `readonly` |

Consumed by `start-qmt.sh` (launch client) and `qmt_mcp.py` (sys.path + trader
path) via `/opt/qmt-mcp/mcp.env`.

## State / Fail-Fast Matrix

| Condition | Outcome |
|---|---|
| `/broker` empty/unreadable | exit non-zero: "broker pack mount /broker is empty/unreadable" |
| `broker.yaml` malformed / bad `schema_version` | exit: parse/version error, no guessing |
| explicit path set but missing | exit: "configured X not found at <path>" |
| client: 0 candidates (no known name) | exit 13: "no QMT client found; set terminal.client" |
| client: top-priority name has >1 copies | exit 13: list candidates, "set terminal.client" |
| client: different names present (e.g. XtItClient + XtMiniQmt) | resolved by priority (XtItClient first); not an error |
| xtquant: 0 found (and not set) | exit: "no xtquant package found in pack" |
| xtquant: >1 found | exit: list candidates, "set xtquant.path" |
| read-only mount | exit: "/broker must be mounted read-write" |
| all resolved | write `/run/qmt/broker.env`, log resolution, continue |
