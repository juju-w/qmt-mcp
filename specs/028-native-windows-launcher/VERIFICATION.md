# Verification: Native Windows Launcher

## Automated release evidence

- PR: <https://github.com/juju-w/qmt-mcp/pull/25>
- Main CI: <https://github.com/juju-w/qmt-mcp/actions/runs/30781696368>
- Release: <https://github.com/juju-w/qmt-mcp/releases/tag/v0.14.0>
- Release workflow: <https://github.com/juju-w/qmt-mcp/actions/runs/30781995192>
- Windows CI built the self-contained x64 ZIP and per-user setup executable,
  imported the embedded Python MCP server, installed the setup silently,
  asserted its installed layout, and uninstalled it silently.
- Downloaded release artifact digests matched the published SHA256 values.

## Real Windows and QMT evidence

Tested on Windows 11 x64 with a logged-in Guangda Jinyangguang QMT 2.1.5
terminal. Broker binaries, SDK files, account data, credentials, and tokens were
kept outside the repository.

- Installed `qmt-mcp-launcher_0.14.0_setup.exe` per user with exit code 0.
- Confirmed the installed `VERSION` is `0.14.0`, the uninstaller registration
  exists in HKCU, and the launcher executable remains alive after startup.
- Confirmed the embedded runtime is CPython 3.12.10 and imports both `qmt_mcp`
  and the official MCP SDK without system Python or .NET prerequisites.
- Confirmed installing and starting the launcher did not stop, restart, or
  duplicate the independently running QMT process.
- Connected the packaged MCP server to a user-supplied CPython 3.12 x64
  `xtquant` SDK and the running QMT `userdata_mini` directory.
- Confirmed authenticated Streamable HTTP health and tool calls report
  `xtquant_import=ok`, `xtdata=ready`, and `qmt_login=logged_in`.
- Confirmed a live `qmt_xtdata_snapshot` call for `510300.SH` returns one quote
  with a last price.
- Confirmed `qmt_xtdata_search_instruments(query="ZGWX", refresh="never")`
  resolves `600118.SH` after applying the Windows cache-sandbox fix.
- Kept xttrade and all write/trading tools disabled during acceptance because
  the test account does not have the required programmatic-trading permission.

## Issue found and resolved

The first real package run exposed a Windows-only cache validation error:
instrument search accepted only the Linux `/broker` sandbox even though the
launcher correctly configured `%LOCALAPPDATA%\QMT-MCP`. The fix preserves the
Linux boundary and adds a platform-specific Windows boundary with traversal,
sibling-prefix, and cross-drive regression tests. Windows packaging now asserts
the native cache path using the embedded Python runtime.

## Remaining manual checks

- Confirm visible first-run controls and tray behavior from the interactive
  desktop session.
- Kill the launcher-owned MCP child and confirm bounded recovery in the UI.
- Export diagnostics and manually inspect the archive for sensitive values.
