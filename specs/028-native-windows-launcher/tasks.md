# Tasks: Native Windows Launcher

## Phase 1 - Specification and architecture

- [x] T001 Define beginner installation, explicit selection, startup,
  readiness, security, diagnostics, and release user stories.
- [x] T002 Record .NET 10/Avalonia 12, per-user tray, DPAPI, native Python,
  bounded discovery, and MCP-first startup decisions.
- [x] T003 Complete constitution check, data model, runtime/release contracts,
  quickstart, and requirements checklist.

## Phase 2 - Solution and cross-platform core

- [x] T004 Create pinned .NET/Avalonia solution structure under `launcher/`.
- [x] T005 Implement launcher profiles, validation, JSON persistence, and
  active-profile rules without plaintext secrets.
- [x] T006 Implement explicit broker resolution plus bounded/cancellable
  discovery with deterministic candidate evidence.
- [x] T007 Implement MCP/terminal command construction, state machine,
  health mapping, redaction, and bounded restart policy behind interfaces.
- [x] T008 Add cross-platform tests for profiles, paths, discovery, state,
  commands, redaction, and supervision.

## Phase 3 - Native Windows integration

- [x] T009 Add current-user DPAPI secret storage and secure token generation.
- [x] T010 Add Windows process discovery, launch/attach identity, singleton,
  per-user paths, clipboard, log opening, and opt-in logon autostart.
- [x] T011 Add rotating launcher/MCP logs and secret-free diagnostics export.
- [x] T012 Add Windows adapter tests and fake terminal/health lifecycle smoke.

## Phase 4 - Avalonia desktop experience

- [x] T013 Implement first-run client selection and resolved-path review.
- [x] T014 Implement operational status, component states, start/stop/retry,
  connection copy, settings, logs, and diagnostics views.
- [x] T015 Implement tray lifecycle, single-instance activation, close-to-tray,
  and active supervision indicators.
- [x] T016 Add macOS demo fixtures and verify desktop/minimum-scale layouts do
  not overlap or resize unexpectedly.

## Phase 5 - Native MCP compatibility

- [x] T017 Adapt MCP filesystem/userdata path handling for native Windows while
  preserving Wine/container behavior.
- [x] T018 Add Python unit tests for native and Wine path resolution and run
  the existing MCP suite.

## Phase 6 - Packaging, CI, and release

- [x] T019 Add pinned Windows Python runtime assembly, checksum verification,
  locked dependency install, server copy, and package-layout smoke.
- [x] T020 Add a per-user Inno Setup installer built from the same stage as ZIP.
- [x] T021 Add macOS/Windows launcher CI for build, tests, publish, fake smoke,
  installer compile, and package assertions.
- [x] T022 Extend automated Release with versioned launcher ZIP/setup assets and
  merged SHA256 checksums without changing existing image/qmtctl delivery.
- [x] T023 Update release policy tests and release documentation for the new
  artifact family.

## Phase 7 - Documentation and verification

- [x] T024 Update root/appliance README, AGENT feature map, and operator skills
  with native Windows installation and security boundaries.
- [x] T025 Run launcher, Python, Go, release-policy, actionlint, conformance,
  Compose/image policy, secret scan, and diff gates.
- [x] T026 Build the Windows release in CI and record artifact/import/installer
  evidence.
- [ ] T027 Install on clean Windows x64 without Docker/Python/.NET and record
  setup, launch, restart, uninstall, and secret-scan evidence.
- [ ] T028 Run real broker QMT login, xtdata smoke, no-duplicate process, MCP
  recovery, and diagnostics acceptance; record any xttrade permission boundary.
- [x] T029 Commit with Conventional Commits, open a PR, and observe PR CI to
  terminal success before merge/release.
- [x] T030 Replace the placeholder icon with a high-contrast Q-and-connector
  mark and verify the embedded ICO sizes on light and dark backgrounds.
- [x] T031 Add persisted Simplified Chinese/English localization for the window,
  runtime states, file pickers, and tray menu.
- [x] T032 Add localization tests, run launcher build/test/UI smoke, and observe
  the updated PR CI to terminal success.

### CI evidence

- PR: <https://github.com/juju-w/qmt-mcp/pull/25>
- Successful run: <https://github.com/juju-w/qmt-mcp/actions/runs/30737685125>
- Windows artifact: `windows-launcher-smoke`, 214,555,366 bytes, containing the
  portable ZIP, per-user setup executable, and launcher checksum manifest.
- Windows smoke: embedded Python import, silent install, installed-layout
  assertions, and silent uninstall all passed on `windows-2025`.
- Bilingual UI run: <https://github.com/juju-w/qmt-mcp/actions/runs/30739059502>
  passed 31 launcher tests, including Simplified Chinese/English persistence,
  Headless+Skia rendering at 940x680 and 760x600, and all nine ICO sizes.
