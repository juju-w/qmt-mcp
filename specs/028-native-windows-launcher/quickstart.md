# Quickstart: Native Windows Launcher Development

## Prerequisites

- .NET 10 SDK on the development host.
- macOS, Linux, or Windows for core/UI development.
- Windows 10 22H2 or Windows 11 x64 for package and real QMT acceptance.
- No QMT or xtquant binary is stored in the repository.

## Restore and test

```bash
dotnet restore launcher/QmtMcp.Launcher.slnx
dotnet build launcher/QmtMcp.Launcher.slnx --configuration Release
dotnet test launcher/QmtMcp.Launcher.slnx --configuration Release
```

## Run the UI on macOS with fixtures

```bash
QMT_LAUNCHER_DEMO=1 \
dotnet run --project launcher/src/QmtMcp.Launcher.Desktop
```

Demo mode uses fake processes and health snapshots. It must never be enabled in
a packaged Windows release.

## Publish the Windows launcher from macOS

```bash
dotnet publish launcher/src/QmtMcp.Launcher.Desktop \
  --configuration Release \
  --runtime win-x64 \
  --self-contained true \
  --output launcher/artifacts/publish/win-x64
```

The compile output can be inspected on macOS. The full package/installer smoke
runs on Windows CI because the Python runtime, DPAPI adapter, and installer need
Windows execution.

## Windows package assembly

```powershell
./launcher/packaging/package-windows.ps1 `
  -Version 0.0.0-dev `
  -Configuration Release `
  -OutputDirectory launcher/artifacts/package
```

The script downloads the pinned official Python runtime into the build cache,
verifies SHA256, installs locked MCP dependencies, copies repository server
source, runs import/package assertions, and creates the versioned ZIP. Inno
Setup compiles the setup EXE from the same stage.

## Real Windows acceptance

1. Install the generated setup EXE as a normal user.
2. Select the broker-provided QMT client executable.
3. Review resolved xtquant and userdata paths; correct them when ambiguous.
4. Select Start. MCP should become live while QMT opens.
5. Complete the normal broker login manually.
6. Copy the MCP connection snippet and run `qmtctl smoke`.
7. Kill only the MCP Python child and verify bounded recovery.
8. Stop the profile and verify independently started QMT remains open.
9. Export diagnostics and scan it for tokens, account IDs, and holdings.

## Required verification

Run the repository-wide commands in `AGENT.md` in addition to launcher tests.
Record clean-VM and live-QMT evidence in this feature's `VERIFICATION.md`.
