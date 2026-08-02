# Feature Specification: Native Windows Launcher

**Feature Branch**: `codex/native-windows-launcher`

**Created**: 2026-08-02

**Status**: In Progress

**Depends on**: 001 (broker resolution), 002 (MCP core), 005
(supervision/readiness), 011 (release delivery), 020 (tool profiles), and 026
(persistent lifecycle semantics).

## Summary

Deliver a broker-neutral Windows desktop companion that runs QMT-MCP without
Docker, Wine, or a user-installed Python. A first-time user selects an existing
broker QMT executable, the launcher resolves its matching `xtquant` and
`userdata_mini`, starts the terminal when necessary, and supervises the native
Windows Python MCP process.

The launcher is a per-user tray application, not a Windows Service. It starts
the MCP endpoint immediately in a truthful degraded state while QMT is opening
or waiting for interactive broker login, then reports ready without requiring a
server restart. It never injects into QMT, captures private ports, stores broker
credentials, or bundles broker software.

## User Scenarios & Testing

### User Story 1 - Start without Docker or Python (Priority: P1)

A Windows user downloads one versioned, checksum-verifiable release package, installs or extracts it,
selects the QMT client already supplied by their broker, and receives a local
MCP URL and token without installing a development toolchain.

**Independent Test**: On a clean Windows 10/11 x64 VM without Docker, Python,
or .NET, install the release package, select a fixture QMT tree, and verify the
launcher starts its bundled Python MCP process.

**Acceptance Scenarios**:

1. **Given** no system Python or .NET runtime, **when** the user installs the
   self-contained package, **then** the launcher opens and requires no separate
   runtime installation.
2. **Given** one or more detected client executables, **when** the user chooses
   one, **then** the launcher shows the resolved client, `xtquant`, userdata,
   and working directory before saving the profile.
3. **Given** auto-detection is ambiguous or incomplete, **when** the user
   continues, **then** the launcher requires explicit paths rather than
   guessing.

### User Story 2 - Launch QMT and reach MCP readiness (Priority: P1)

The user starts one launcher profile. MCP becomes reachable locally, QMT is
started if absent, and the launcher transitions from waiting for login to ready
after the user completes the normal broker login.

**Independent Test**: Use fake terminal and health processes to validate every
state transition on macOS/CI, then run the same flow against a real QMT client
on Windows.

**Acceptance Scenarios**:

1. **Given** QMT is stopped, **when** Start is selected, **then** exactly one
   configured QMT process and one MCP child process are launched.
2. **Given** QMT is already running from the configured executable, **when**
   Start is selected, **then** the launcher attaches to that process and does
   not start a duplicate.
3. **Given** broker login is pending, **when** MCP health is queried, **then**
   liveness succeeds while xtdata reports degraded or login-required.
4. **Given** the user completes login, **when** the readiness probe succeeds,
   **then** the launcher reaches ready without restarting MCP.
5. **Given** the MCP child exits unexpectedly, **when** supervision is active,
   **then** it is restarted with bounded backoff and the failure remains visible.

### User Story 3 - Keep the local endpoint secure (Priority: P1)

The default setup is safe for a non-technical user: MCP listens only on host
loopback, uses a generated bearer token, and does not leak tokens, account IDs,
or broker credentials into logs or profile JSON.

**Independent Test**: Inspect process arguments, environment summaries, config,
logs, and listeners after first run and restart.

**Acceptance Scenarios**:

1. **Given** a new profile, **when** it is saved, **then** a cryptographically
   random token is protected for the current Windows user and omitted from the
   profile document.
2. **Given** default settings, **when** MCP starts, **then** it binds only to
   `127.0.0.1` and creates no firewall rule.
3. **Given** logs or diagnostics are exported, **when** they are inspected,
   **then** bearer tokens, broker login secrets, account IDs, and holdings are
   absent or redacted.
4. **Given** the user requests the connection snippet, **when** it is copied,
   **then** the token is revealed only through that deliberate local action.

### User Story 4 - Diagnose and recover locally (Priority: P2)

The user can see whether the terminal, MCP server, xtdata, and optional xttrade
query connection are stopped, starting, waiting, ready, degraded, or failed.

**Independent Test**: Exercise missing paths, login wait, occupied port,
permission failure, terminal exit, MCP crash, and malformed health responses.

**Acceptance Scenarios**:

1. **Given** a startup failure, **when** the status view opens, **then** it names
   the failed component and provides a secret-free actionable reason.
2. **Given** a corrected path or released port, **when** Retry is selected,
   **then** the launcher recovers without reinstalling.
3. **Given** the user exports diagnostics, **when** the archive is created,
   **then** it contains versions, resolved non-secret paths, state history, and
   bounded logs only.
4. **Given** the user stops the launcher-managed service, **when** QMT was
   already running independently, **then** QMT remains open by default.

### User Story 5 - Receive the launcher in normal releases (Priority: P2)

Each project release includes a Windows x64 launcher archive and installer next
to qmtctl artifacts, with checksums and reproducible version metadata.

**Independent Test**: Run the packaging workflow on `windows-latest`, inspect
the staged tree, install and uninstall silently in a VM, and verify checksums.

**Acceptance Scenarios**:

1. **Given** a release version, **when** packaging runs, **then** the launcher,
   pinned Python runtime, locked MCP dependencies, server source, notices, and
   license are assembled from declared inputs.
2. **Given** the generated archive and installer, **when** executed on clean
   Windows x64, **then** neither Docker nor system Python/.NET is required.
3. **Given** GitHub Release publication, **when** assets are listed, **then** the
   launcher ZIP, installer, and their SHA256 entries are present.

## Functional Requirements

- **FR-001**: The launcher MUST target Windows 10 22H2 and Windows 11 on x64.
- **FR-002**: The launcher MUST be broker-neutral and MUST NOT contain QMT,
  MiniQMT, `xtquant`, broker binaries, account data, or broker credentials.
- **FR-003**: The release MUST include the launcher, a pinned Windows Python
  3.12 runtime, locked MCP runtime dependencies, and repository MCP source.
- **FR-004**: First run MUST support explicit selection of `XtItClient.exe`,
  `XtMiniQmt.exe`, or a compatible broker client executable.
- **FR-005**: Auto-discovery MUST be bounded, cancellable, and combine running
  processes, saved profiles, and common install roots without recursively
  indexing an entire disk without limits.
- **FR-006**: Resolution MUST produce a client executable, client working
  directory, `xtquant` import root, userdata path, and broker-neutral profile ID.
- **FR-007**: Explicit user paths MUST win over detection; invalid or ambiguous
  inputs MUST fail closed with candidate details.
- **FR-008**: The launcher MUST verify the client exists and that the resolved
  import root contains `xtquant/__init__.py` before allowing Start.
- **FR-009**: The launcher MUST use a single-instance lock per user and prevent
  duplicate QMT or MCP children for one profile.
- **FR-010**: MCP MUST start independently of broker login and expose truthful
  liveness/readiness while QMT is starting or awaiting interaction.
- **FR-011**: The terminal MUST start in the interactive logged-in user session
  with its own executable directory as working directory.
- **FR-012**: The launcher MUST attach to a matching running terminal instead of
  starting a second copy.
- **FR-013**: The launcher MUST NOT automate account passwords, captcha, MFA,
  agreements, upgrades, or trading dialogs.
- **FR-014**: The MCP child environment MUST provide native Windows xtquant and
  userdata paths without Wine path conversion.
- **FR-015**: The launcher MUST supervise MCP with bounded exponential backoff,
  preserve state history, and stop retrying after a configurable failure limit.
- **FR-016**: Unexpected QMT exit MUST be reported and MAY be retried only when
  the launcher originally started that process and the user enabled restart.
- **FR-017**: Stopping MCP MUST NOT close an independently started QMT process;
  closing launcher UI MUST minimize to tray while supervision is active.
- **FR-018**: New profiles MUST bind MCP to `127.0.0.1`; non-loopback exposure
  and automatic firewall changes are out of scope for the first release.
- **FR-019**: Each profile MUST use a generated token of at least 256 bits.
- **FR-020**: Production Windows MUST protect tokens with current-user DPAPI or
  an equivalent Windows credential facility and MUST not store plaintext tokens
  in profile JSON, logs, command lines, or exported diagnostics.
- **FR-021**: Profile and runtime state MUST live under per-user local app data;
  no administrator permission or write access to Program Files is required.
- **FR-022**: The UI MUST expose component status, resolved paths, local MCP URL,
  start/stop/retry, connection snippet copy, logs, and diagnostics export.
- **FR-023**: Logs MUST be rotating, bounded, UTF-8, and redact configured secret
  values and bearer headers.
- **FR-024**: The first release MUST support one active profile; additional
  profiles may be saved but simultaneous multi-terminal management is deferred.
- **FR-025**: The runtime path adapter MUST preserve existing Wine/container
  behavior while accepting native Windows paths.
- **FR-026**: Core discovery, resolution, state machine, redaction, command
  construction, and supervision policy MUST be host-testable on macOS/Linux.
- **FR-027**: Windows CI MUST test build, self-contained publish, package layout,
  installer compilation, and a fake-terminal/fake-health lifecycle smoke.
- **FR-028**: Release assets MUST include a versioned Windows x64 ZIP, a per-user
  installer EXE, and entries in the release SHA256 manifest.
- **FR-029**: Package inputs and versions MUST be pinned; build scripts MUST
  verify downloaded Python runtime integrity before assembly.
- **FR-030**: Existing Docker appliance, MCP tool contracts, qmtctl packages,
  read-only defaults, and automated release behavior MUST remain compatible.

## Non-Goals

- Bundling, downloading, patching, or updating a broker QMT terminal or xtquant.
- Automating broker login, captcha, MFA, agreements, credentials, or trading.
- A Windows Service that launches QMT in Session 0.
- Public internet exposure, TLS termination, firewall automation, or LAN mode.
- Running multiple QMT terminals concurrently in the first release.
- Supporting Windows ARM64, Windows Server Core, Windows 7/8, or 32-bit QMT.
- Rewriting the Python MCP server or proprietary xtquant binding in C#.
- Automatic in-app updates in the first release.

## Success Criteria

- On clean Windows x64 without Docker, Python, or .NET, the launcher opens and
  creates a valid profile in under three minutes.
- MCP liveness is reachable within ten seconds of Start; after normal QMT login,
  xtdata readiness is reflected within sixty seconds without MCP restart.
- Repeated Start operations preserve one MCP child and at most one configured
  QMT process.
- Killing the MCP child demonstrates bounded recovery and visible diagnostics.
- Token scans find no plaintext secret in profiles, logs, process arguments, or
  diagnostic archives.
- macOS core tests, Windows launcher tests/package smoke, full repository CI,
  and the automated GitHub Release all complete successfully.
