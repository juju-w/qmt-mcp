# Implementation Plan: Secure Persistent Desktop

**Branch**: `codex/026-persistent-desktop` | **Date**: 2026-07-31 |
**Spec**: `specs/026-persistent-desktop/spec.md`

## Summary

Upgrade the appliance from Ubuntu Noble's obsolete xrdp 0.9 packages to pinned
upstream xrdp 0.10.6.1 and xorgxrdp 0.10.5, harden the RDP boundary, and add an
opt-in persistent desktop mode. The preferred implementation securely invokes
`xrdp-sesrun` to create one Xorg/XFCE session before any client connects; a
later Windows App connection must reattach that exact session.

The first implementation activity is a disposable native amd64 POC. If the POC
cannot prove same-session reattachment, implementation stops and this plan is
revised. VNC is not an automatic fallback.

## Technical Context

**Language/Version**: Bash, Dockerfile, xrdp ini, Compose YAML, and existing
Python 3.12 health/test helpers where structured parsing is needed.

**Primary Dependencies**: Wine 11 stable base, XFCE, Xorg, xrdp 0.10.6.1,
xorgxrdp 0.10.5, OpenSSL, PAM, gosu, and Docker Compose.

**Storage**: Existing read-write broker pack; `/run/qmt/desktop` for ephemeral
lifecycle state; one instance-scoped persistent volume or mounted directory for
the RDP certificate and private key; Docker secret/file for the RDP password.

**Testing**: Shell/unit fixtures, container inspection, TLS/RDP scanners,
FreeRDP automation, Windows App manual acceptance, process/session assertions,
native linux/amd64 image smoke, and all existing Python/Go/CI gates.

**Target Platform**: Native linux/amd64 NAS container; macOS Windows App and
FreeRDP clients.

**Performance Goals**: No material interaction regression from current xrdp;
one disconnected desktop with bounded idle CPU; persistent boot to desktop and
MCP liveness within 120 seconds when QMT state is reusable.

**Constraints**: One Wine prefix, one broker pack, one desktop user, one QMT,
one MCP supervisor, no broker-credential automation, no public RDP, no VNC, and
no floating package or base-image versions.

**Scale/Scope**: One desktop session per appliance instance; multiple appliance
instances remain isolated by container, ports, secrets, certificate storage,
broker pack, and runtime state.

## Constitution Check

- **I Broker-agnostic**: PASS. Desktop lifecycle and RDP hardening contain no
  broker terminal or data; the existing runtime broker pack remains variable.
- **II Read-only default**: PASS. No MCP or trading tool is added. The desktop
  remains capable of normal human QMT interaction, as it is today.
- **III Reproducible pinned builds**: PASS with required work. Official xrdp and
  xorgxrdp sources, versions, and hashes are pinned in a build stage; image
  smoke asserts exact runtime versions.
- **IV Contract-first MCP**: PASS. MCP tool contracts are unchanged.
- **V Observable/readiness-gated**: PASS. Desktop lifecycle becomes observable;
  MCP liveness remains separate from xtdata/QMT readiness.
- **VI Security by default**: PASS after implementation. Loopback publishing,
  TLS-only transport, unique keys, no default password, least privilege, and
  restricted channels replace the current development defaults.
- **VII Spec-driven delivery**: PASS. 026 is isolated from PR #19 and no runtime
  implementation begins before owner approval plus the POC gate.

## Architecture

### Build and package boundary

Use a dedicated builder stage based on the same pinned Ubuntu/Wine lineage:

1. Fetch official xrdp 0.10.6.1 and xorgxrdp 0.10.5 source archives.
2. Verify committed SHA-256 values before extraction.
3. Build with only required Xorg, PAM, TLS, JPEG/RFX/GFX, and channel features.
4. Install into a staging root or produce deterministic packages.
5. Copy/install runtime output into the final image and remove Noble 0.9
   packages without leaving compilers or source trees.
6. Assert `xrdp --version`, module load, TLS support, and xorgxrdp ABI in the
   build-time smoke.

The date-pinned Wine base remains pinned. A later base tag is evaluated through
the existing Wine/QMT smoke and is not assumed to solve xrdp packaging.

### Session ownership

The entrypoint remains root only for configuration, PAM/session management,
certificate permissions, and privilege drop. It starts xrdp-sesman and xrdp,
then persistent mode invokes a dedicated bootstrap helper:

1. Resolve the password from an owner-only file or compatibility environment.
2. Validate the RDP policy before starting the listener.
3. Wait for the local sesman control endpoint.
4. Acquire an exclusive desktop lease.
5. Feed the password to `xrdp-sesrun -F 0` without argv exposure.
6. Discover and verify the resulting session, display, XFCE, QMT, and MCP.
7. Publish secret-free lifecycle state and supervise bounded recovery.

The exact PID 1 arrangement is selected by the POC. Prefer an existing or
pinned minimal init/subreaper only if xrdp cannot own/reap its full process tree
cleanly. Do not add a general process manager without evidence.

### Same-session enforcement

- Configure a dedicated terminal-server group with only `wineuser`.
- Set the xrdp session policy to rejoin the user's existing Xorg session.
- Keep disconnected sessions alive.
- Force/normalize supported color depth where needed for deterministic policy.
- Add kernel file locks to `start-qmt.sh` and `qmt-supervisor.sh`.
- Treat a second Xorg or QMT root as a failed invariant, not a valid `both`
  mode.

### RDP boundary

- Compose publishes `127.0.0.1:${RDP_PORT}:3389` by default.
- Non-loopback publishing requires explicit acknowledgement and audit evidence
  for VPN/firewall restriction.
- xrdp enforces TLS 1.2/1.3 with a unique persisted per-instance key.
- No built-in password is accepted.
- Desktop sudo, root RDP login, broad login users, drive/file channels, and
  broad clipboard are removed from the default profile.
- Existing TLS compose is converted to a true override or shared anchor/model
  so it cannot drift from the base service definition.

## Project Structure

```text
specs/026-persistent-desktop/
├── spec.md
├── research.md
├── data-model.md
├── plan.md
├── tasks.md
├── quickstart.md
├── contracts/
│   └── desktop-session.md
└── checklists/
    └── requirements.md

appliance/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.tls.yml
├── .env.example
├── scripts/
│   ├── qmt-entrypoint.sh
│   ├── bootstrap-rdp-session.sh
│   ├── desktop-healthcheck.sh
│   ├── harden-check.sh
│   ├── start-qmt.sh
│   └── qmt-supervisor.sh
├── config/xrdp/
│   ├── xrdp.ini
│   └── sesman.ini
└── tests/
    ├── test-desktop-config.sh
    ├── test-desktop-lifecycle.sh
    └── test-rdp-security.sh

appliance/mcp/tests/integration/
└── test_desktop_health.py

docs/
└── [deployment and MCP client references]

skills/qmt-mcp-ops/
└── SKILL.md
```

**Structure Decision**: Keep operating-system lifecycle in appliance scripts
and ini templates. Do not move RDP orchestration into the Wine Python MCP. A
small Python test/helper is allowed only where process/status JSON parsing is
safer than shell.

## Implementation Phases

1. Build a disposable pinned xrdp 0.10.6.1/xorgxrdp 0.10.5 image and complete
   the session-reattach POC on native amd64.
2. Benchmark RFX/GFX/H.264 behavior with QMT and select a conservative codec
   policy for the NAS and macOS client.
3. Land the reproducible package build/version gate and hardened xrdp/sesman
   configuration.
4. Add secret resolution, per-instance certificate bootstrap, loopback Compose
   default, no-sudo desktop, login group, and channel policy.
5. Add persistent/manual lifecycle, session discovery, singleton leases,
   bounded recovery, status, and health checks.
6. Add shell/container tests plus native attach/detach/restart acceptance.
7. Update deployment docs, examples, AGENT, and operations skill.
8. Run full CI, native image build, live non-production rollout, PR CI, main CI,
   and automated release observation.

## POC Exit Criteria

All must pass before Phase 3:

- `xrdp-sesrun -F 0` starts XFCE autostart without argv secret exposure.
- Windows App attaches to the pre-created session.
- Attach/disconnect/reattach preserves display and QMT process identity.
- One supported resolution change does not create a second session.
- Container stop/restart leaves no unrecoverable pidfile/socket state.
- Five POC restarts produce no duplicate QMT or MCP.

If any same-session criterion fails, stop and revise the architecture. The
fallback investigation may test a loopback FreeRDP client, but VNC requires a
new approved spec.

## Verification Strategy

- Static: shell syntax/ShellCheck, Dockerfile lint, Compose render, no secret
  values, exact package/hash checks, and `git diff --check`.
- Unit: config validation, password-file handling, status serialization,
  singleton races, stale state, retry budget, and signal cleanup.
- Container: TLS-only negotiation, unique certificate, group/sudo/channel
  policy, host bind rendering, process count, and negative unsafe fixtures.
- Native: cold boot, manual QMT login, MCP liveness/readiness, FreeRDP plus
  Windows App attach/reconnect, 30-minute disconnect, resolution change, and
  ten recreates.
- Regression: all Python/Go tests, protocol conformance, actionlint, release
  policy, secret scan, image smoke, and six-target qmtctl builds.

## Compatibility Strategy

- `QMT_DESKTOP_MODE=manual` preserves the operator-created session workflow for
  migration and diagnosis.
- `persistent` is opt-in until native evidence and one release cycle establish
  it; the target deployment may enable it immediately after acceptance.
- `QMT_RDP_PASSWORD` remains a compatibility input with no default and a
  deprecation warning; file-backed secrets are preferred.
- Broker packs and QMT login data are not migrated.
- Removing the `qmt` password and wildcard RDP bind is an intentional secure
  default change and requires release notes.

## Complexity Tracking

| Complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Build pinned xrdp/xorgxrdp from official source | Noble public packages remain vulnerable and Ubuntu's fixes require ESM | Installing `apt xrdp` reproduces the known 0.9.24 exposure |
| Pre-create an xrdp-managed Xorg session | Operator must attach to the same running QMT desktop after unattended boot | Xvfb alone cannot be attached by the current xrdp path; VNC adds a slower insecure protocol |
| Per-instance TLS key storage | The inherited image key is shared and cannot identify an instance | A baked snakeoil key makes every deployment share public key material |
| Singleton and lifecycle supervision | RDP races and restarts must never run two QMTs against one Wine prefix | Comments/documentation do not enforce the process invariant |
