# Contract: Native Windows Launcher

## Profile File

Location: `%LOCALAPPDATA%\QMT-MCP\profiles.json`

```json
{
  "schemaVersion": 1,
  "activeProfileId": "guangda-jinyangguang",
  "profiles": [
    {
      "schemaVersion": 1,
      "id": "guangda-jinyangguang",
      "displayName": "QMT",
      "clientPath": "D:\\QMT\\bin.x64\\XtItClient.exe",
      "workingDirectory": "D:\\QMT\\bin.x64",
      "xtquantRoot": "D:\\QMT",
      "userdataPath": "D:\\QMT\\userdata_mini",
      "mcpHost": "127.0.0.1",
      "mcpPort": 18765,
      "tokenSecretId": "secret_<random>",
      "autoStartLauncher": false,
      "restartTerminal": false,
      "createdAt": "2026-08-02T00:00:00Z",
      "updatedAt": "2026-08-02T00:00:00Z"
    }
  ]
}
```

Unknown schema versions fail closed. Unknown additive fields in schema version
1 are ignored for forward compatibility. Token plaintext and account IDs are
forbidden.

## Resolution Result

```text
Resolve(clientPath, optional xtquantRoot, optional userdataPath)
  -> Success(ResolvedBroker, evidence[])
  -> Failure(code, candidates[], actionableMessage)
```

Stable failure codes:

| Code | Meaning |
|---|---|
| `client_missing` | Selected executable does not exist |
| `client_unsupported` | Path is not a Windows executable |
| `xtquant_missing` | No `xtquant/__init__.py` below accepted roots |
| `xtquant_ambiguous` | More than one equal-confidence import root |
| `userdata_missing` | Explicit userdata path does not exist or cannot be created |
| `path_not_absolute` | Any required path is relative |
| `profile_invalid` | Host, port, secret reference, or schema is invalid |

## MCP Child Contract

Executable:

```text
<install>\runtime\python\python.exe -u <install>\server\qmt_mcp.py
```

Required environment additions:

| Variable | Value |
|---|---|
| `PYTHONPATH` | `<install>\server;<profile.xtquantRoot>` |
| `QMT_XTQUANT_DIR_WIN` | Native absolute `xtquantRoot` |
| `QMT_USERDATA_WIN` | Native absolute userdata path |
| `QMT_BROKER_ID` | Non-secret profile ID |
| `MCP_HOST` | `127.0.0.1` |
| `MCP_PORT` | Validated profile port |
| `QMT_MCP_TOKEN` | Decrypted token, environment only |
| `QMT_MCP_AUTH_MODE` | `static` |
| `QMT_MCP_AUDIT_PATH` | Per-user logs path |
| `QMT_MCP_TASK_STORE` | Per-user state path |
| `QMT_INSTRUMENT_CACHE_PATH` | Per-user cache path |

The token must not appear in argv or startup logs. Child stdout/stderr are
captured and redacted before persistence.

## Terminal Child Contract

- Executable is exactly the resolved client path.
- Working directory is exactly the resolved client directory.
- Launch occurs in the current interactive user session.
- No account/password/captcha argument is supplied.
- A process whose normalized executable path matches is attached, not duplicated.
- Stop does not terminate an attached process. A launched process is also kept
  open by default unless the user explicitly requests terminal shutdown.

## Health Mapping

| Observation | Launcher state |
|---|---|
| MCP process absent during retry | `degraded` |
| `/livez` unavailable during startup grace | `startingMcp` |
| `/livez` healthy, xtdata not ready | `waitingForLogin` |
| `/healthz` xtdata ready | `ready` |
| MCP live with an optional family unavailable | `degraded` with component detail |
| Retry budget exhausted | `faulted` |

Polling uses a bounded timeout and cancellation token. Malformed or
unauthenticated health responses never become ready.

## Release Artifacts

For version `X.Y.Z`:

```text
qmt-mcp-launcher_X.Y.Z_windows_x64.zip
qmt-mcp-launcher_X.Y.Z_setup.exe
SHA256SUMS
```

Both launcher artifacts contain the same staged application version. The ZIP
root contains `QmtMcp.Launcher.exe`, `runtime/python`, `server`, `LICENSE`, and
`README.txt`. The installer uses `{localappdata}\Programs\QMT-MCP`, creates
Start Menu/uninstall entries, and does not require elevation.
