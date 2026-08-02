# Research: Native Windows Launcher

## Decision 1: .NET 10 and Avalonia 12.1

Use C#/.NET 10 with Avalonia 12.1 rather than WinUI, WPF, or a webview shell.
Modern .NET 10 is an LTS release through November 2028. Avalonia uses Win32
directly on Windows, supports a native tray menu, targets ordinary `net10.0`,
and can cross-compile Windows output from macOS/Linux without a Windows desktop
workload.

Sources:

- https://learn.microsoft.com/en-us/lifecycle/products/microsoft-net-and-net-core
- https://docs.avaloniaui.net/docs/platform-specific-guides/windows
- https://docs.avaloniaui.net/controls/navigation/trayicon
- https://www.nuget.org/packages/Avalonia.Desktop/12.1.0

Rejected alternatives:

- WinUI 3 is Microsoft's preferred new native Windows UI, but its productive
  toolchain and platform acceptance remain Windows-centric.
- Tauri 2 is capable but adds a web frontend and WebView2 lifecycle to a small
  system utility whose main work is process/configuration integration.
- WPF/WinForms are supported but do not improve Mac-first development.
- A CLI alone does not satisfy first-run discovery, visible login waiting, tray
  supervision, or beginner-friendly diagnostics.

## Decision 2: Per-user tray process, not a Windows Service

QMT is an interactive GUI terminal and may show login, captcha, agreement, or
upgrade dialogs. Launch it from the signed-in user's tray process so it remains
in the same desktop session. A Session-0 Windows Service is unsuitable for the
terminal lifecycle. The launcher may register itself for current-user logon,
but autostart remains opt-in.

## Decision 3: Reuse the Python MCP server

Keep `appliance/mcp/qmt_mcp.py` and its packages as the single MCP
implementation. XtQuant officially runs as a local Python library and requires
MiniQMT to be started first. Xttrade uses the terminal's full `userdata_mini`
path and a unique session ID. The Windows launcher supplies those paths and
starts the same server under native CPython rather than Wine CPython.

Sources:

- https://dict.thinktrader.net/nativeApi/start_now.html
- https://dict.thinktrader.net/nativeApi/xttrader.html
- https://dict.thinktrader.net/nativeApi/question_function.html

## Decision 4: MCP starts before terminal readiness

Start MCP immediately, then launch or attach to QMT. Existing readiness logic
already separates liveness from xtdata/trader readiness. This gives agents a
stable endpoint and actionable `login_required`/degraded state instead of a
connection refusal while a human completes normal broker login.

## Decision 5: Explicit selection wins over bounded discovery

The first-run file picker is the authoritative path. Auto-discovery improves
convenience but remains bounded and cancellable:

1. Reuse valid saved profiles.
2. Inspect matching running process executable paths where permissions allow.
3. Search configured common roots to a depth/file/time limit for known client
   names.
4. Resolve userdata beside the QMT root and locate an import root containing
   `xtquant/__init__.py`.
5. Return candidates and require user choice whenever confidence is not unique.

Do not crawl every disk indefinitely, infer from window titles, inject into a
process, or scrape internal QMT ports.

## Decision 6: DPAPI and local app data

Store non-secret profile data under `%LOCALAPPDATA%\QMT-MCP`. Protect each bearer
token for the current Windows user with DPAPI and keep the ciphertext separate
from profile JSON. Reveal plaintext only for deliberate copy/config actions.
Development fakes provide deterministic secret storage on macOS; production
must fail closed when the Windows protector is unavailable.

## Decision 7: Official embeddable Python plus locked packages

Assemble release runtime from pinned Python 3.12.10 x64 embeddable ZIP and the
existing hash-locked `appliance/mcp/requirements.txt`. Windows CI verifies the
download checksum, installs packages into a staged `Lib/site-packages`, enables
site import in `python312._pth`, and validates server imports before packaging.

This keeps the target independent of system Python and avoids committing large
runtime binaries. The runtime stays x64 to match QMT and xtquant native modules.

## Decision 8: Self-contained launcher, ZIP, and per-user installer

Publish the Avalonia launcher self-contained for `win-x64`, initially without
trimming or NativeAOT. Dynamic UI/platform behavior is safer before AOT tuning,
and Python dominates package size. Create one portable ZIP and one Inno Setup
installer from the exact same staged directory. The installer uses current-user
local app data, creates normal shortcuts, and requires no administrator rights.

Sources:

- https://learn.microsoft.com/en-us/dotnet/core/deploying/single-file/overview
- https://docs.avaloniaui.net/docs/deployment/native-aot

## Decision 9: One active profile in the first release

Allow multiple saved profiles but supervise only one at a time. Xtdata may
select among multiple QMT instances and broker installations vary substantially;
simultaneous profile isolation needs explicit port/session research and belongs
in a later feature. The UI must stop the active MCP child before switching.
