# Implementation Plan: Native Windows Launcher

**Branch**: `codex/native-windows-launcher` | **Date**: 2026-08-02 |
**Spec**: `specs/028-native-windows-launcher/spec.md`

## Summary

Add a .NET 10/Avalonia 12 per-user desktop launcher that resolves an externally
installed QMT terminal, starts the existing Python MCP server with native
Windows paths, supervises readiness, and ships as Windows x64 ZIP and installer
assets in the existing automated release.

## Technical Context

**Language/Version**: C# 14 on .NET 10; Python 3.12.10 for the bundled MCP
runtime; PowerShell for Windows package assembly; Inno Setup for the installer.

**UI**: Avalonia 12.1.0 with the Fluent theme, a tray-first desktop shell, and
runtime-switchable Simplified Chinese/English resource catalogs.

**Dependencies**: Existing `appliance/mcp` server source and hash-locked Python
requirements; Windows DPAPI; Avalonia storage provider; GitHub Actions Windows
runner; existing release policy.

**State**: `%LOCALAPPDATA%\QMT-MCP\profiles.json`, protected secret blobs,
rotating launcher/MCP logs, and ephemeral child-process state.

**Target**: Windows 10 22H2/Windows 11 x64. macOS is the primary development
host for UI/core tests; Windows CI and a real Windows QMT host provide platform
acceptance.

**Constraints**: No broker binaries in Git/release, no system Python/.NET
requirement, no admin requirement, loopback only, one active profile, no login
automation, no Session-0 service.

## Constitution Check

- **I Broker-agnostic**: PASS. The launcher stores only user-selected paths and
  never packages terminal, xtquant, userdata, or broker identity assumptions.
  A native profile is the Windows equivalent of selecting an external broker
  pack; switching profiles requires no source or release rebuild.
- **II Read-only default**: PASS. The launcher inherits current MCP profiles and
  feature gates. It adds no order, cancel, transfer, or credential automation.
- **III Reproducible pinned builds**: PASS. .NET, Avalonia, Python, requirements,
  package scripts, and installer inputs are pinned and assembled in CI.
- **IV Contract-first MCP**: PASS. Existing tool schemas/docstrings are reused;
  the launcher adds no hidden MCP surface.
- **V Observable/readiness-gated**: PASS. The launcher state machine separates
  process liveness, broker login, xtdata readiness, and xttrade authorization.
- **VI Security by default**: PASS. Per-user DPAPI, loopback bind, generated
  token, redacted diagnostics, and no firewall rule are defaults.
- **VII Spec-driven delivery**: PASS. Spec, research, data model, contracts,
  quickstart, and tasks precede implementation.

## Architecture

```text
QmtMcp.Launcher.Desktop (Avalonia UI/tray)
        |
QmtMcp.Launcher.Core (profiles, discovery, state machine, supervision)
        |
QmtMcp.Launcher.Windows (DPAPI, process/registry integration)
        |
bundled python.exe -> existing appliance/mcp/qmt_mcp.py -> local QMT/xtquant
```

1. `Core` contains no Avalonia or Windows dependency. Filesystem, process,
   secret, clock, and HTTP operations are interfaces with deterministic tests.
2. `Windows` resolves current-user paths, DPAPI secrets, running executable
   identity, and optional logon autostart. It is selected only on Windows.
3. `Desktop` provides setup, status, settings, diagnostics, and tray lifecycle.
4. MCP starts from a bundled Python 3.12 runtime with environment-only runtime
   configuration. Its stdout/stderr are redirected to bounded local logs.
5. The existing readiness probe accepts native Windows paths. Launcher health
   polling maps `/livez` and `/healthz` into a user-facing state machine.
6. Package assembly downloads the pinned official Python embeddable ZIP,
   verifies SHA256, installs hash-locked requirements into `Lib/site-packages`,
   copies MCP source, and combines that tree with self-contained launcher output.
7. Inno Setup wraps the same staged tree in a per-user installer; ZIP and setup
   artifacts are uploaded into the existing release job and checksum manifest.

## Project Layout

```text
launcher/
├── Directory.Build.props
├── Directory.Packages.props
├── QmtMcp.Launcher.slnx
├── src/
│   ├── QmtMcp.Launcher.Core/
│   ├── QmtMcp.Launcher.Windows/
│   └── QmtMcp.Launcher.Desktop/
├── tests/QmtMcp.Launcher.Core.Tests/
├── packaging/
│   ├── package-windows.ps1
│   └── qmt-mcp-launcher.iss
└── README.md
```

## Implementation Phases

1. Add solution/package policy and cross-platform domain model.
2. Implement bounded discovery, explicit resolution, profile persistence,
   token abstraction, process command construction, state machine, and tests.
3. Add native Windows DPAPI/process/autostart adapters.
4. Add Avalonia setup/status/settings/diagnostics shell and tray behavior.
5. Adapt MCP runtime paths for native Windows without regressing Wine.
6. Add deterministic package assembly, installer, CI matrix, and release assets.
7. Run macOS tests, Windows CI smoke, clean-VM acceptance, and real-QMT smoke.

## Verification Strategy

- **Core**: .NET unit tests for discovery bounds, resolution precedence,
  persistence, state transitions, backoff, redaction, and command environment.
- **Python**: existing unit/integration tests plus native/Wine path-adapter tests.
- **Desktop**: build on macOS and Windows; headless view-model tests where
  behavior matters; manual screenshot/layout check on both platforms.
- **Windows smoke**: fake QMT executable and fake MCP health server validate
  singleton, launch/attach, login-wait, ready, crash/restart, and stop behavior.
- **Packaging**: verify exact staged files, Python import, MCP source import,
  version metadata, installer compile, uninstall, and SHA256 output.
- **Regression**: all existing Python, Go, release policy, actionlint,
  conformance, secret scanning, Compose, and image gates.
- **Real acceptance**: Windows x64 with broker QMT, manual login, xtdata query,
  launcher restart, diagnostics export, and no-duplicate process checks.

## Release Integration

- Add a CI launcher job for macOS tests and Windows build/package smoke.
- Add a release `windows-launcher` job using the tagged release SHA.
- Publish `qmt-mcp-launcher_<version>_windows_x64.zip` and
  `qmt-mcp-launcher_<version>_setup.exe`.
- Merge launcher hashes into the release `SHA256SUMS`; preserve all existing
  qmtctl assets and appliance image behavior.
- Keep signing optional until repository signing credentials are configured;
  unsigned artifacts must be identified plainly and remain checksum-verifiable.

## Complexity Tracking

| Complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Avalonia desktop shell | Mac-first development plus Windows tray/setup UI | WinUI requires a Windows-centric toolchain; CLI-only is not suitable for beginners |
| Bundled Python runtime | xtquant and the existing MCP server require CPython ABI compatibility | Rewriting the MCP and proprietary binding in C# is infeasible and duplicates mature code |
| Windows adapter layer | DPAPI, process identity, and logon startup are platform-specific | Putting platform checks throughout UI/core would make tests brittle |
| Two release formats | ZIP supports portable/diagnostic use; installer supports beginners | A ZIP alone leaves setup, shortcuts, and uninstall as manual work |
| MCP-first degraded startup | Endpoint remains observable while broker login waits | Waiting to start MCP makes clients see only connection failures during normal login |
