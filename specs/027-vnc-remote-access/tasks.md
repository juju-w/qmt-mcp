# Tasks: VNC Remote Access

## Phase 1 - Specification and PR review

- [x] T001 Correct the requirement from unattended startup to first-class VNC
  credential persistence and cross-platform/mobile client access.
- [x] T002 Review PR #19 and record the useful raw-VNC, XFCE, supervision, and
  resource choices plus the separate-session and security gaps.
- [x] T003 Define the one-display RDP/VNC contract, configuration, secrets,
  status, failure isolation, and native acceptance criteria.
- [x] T004 Complete the constitution check, plan, research, quickstart, and
  requirements checklist.

## Phase 2 - Image and secure configuration

- [x] T005 Install x11vnc and the stdin-capable TigerVNC password utility in the
  stable runtime dependency layer and extend the image gate.
- [x] T006 Add fail-closed VNC enablement, persistent-mode, bind, password-file,
  compatibility password, RDP fallback, and redaction logic to entrypoint.
- [x] T007 Generate the ephemeral mode-0600 VNC auth file through stdin and
  prove no plaintext appears in argv, `mcp.env`, status, or logs.
- [x] T008 Add VNC environment to the shared service without changing default
  port publication.
- [x] T009 Add an opt-in loopback-first VNC Compose override and LAN gate.

## Phase 3 - Same-session VNC lifecycle

- [x] T010 Start x11vnc against the discovered persistent Xorg display and
  Xauthority with shared reconnect, QMT repaint/keyboard, no file transfer,
  no remote commands, and disabled clipboard defaults.
- [x] T011 Add VNC readiness and PID to atomic desktop status schema version 2.
- [x] T012 Add bounded x11vnc-only restart and graceful shutdown without
  changing Xorg, QMT, MCP, xrdp, or sesman identities.
- [x] T013 Preserve disabled/default and manual-mode behavior exactly.

## Phase 4 - Tests and documentation

- [x] T014 Add unit/static tests for enablement, password sources, permission
  failures, redaction, bind gates, x11vnc flags, status, and restart behavior.
- [x] T015 Extend Compose CI assertions for no default VNC port and loopback
  VNC override publication.
- [x] T016 Extend image verification for x11vnc/TigerVNC without noVNC or
  build-tool leakage.
- [x] T017 Extend hardening checks for VNC secret, mode, bind, raw-transport,
  adapter process, and shared-session invariants.
- [x] T018 Update root/appliance README, deployment docs, AGENT, `.env.example`,
  and qmt operations/deployment skills with saved-client and Android workflows.

## Phase 5 - Verification and delivery

- [x] T019 Run Python, Go, protocol conformance, release-policy, actionlint,
  ShellCheck, Compose, image, secret-scan-equivalent, and diff gates.
- [x] T020 Build on native amd64 NAS and authenticate with a real VNC client
  through loopback/tunnel.
- [x] T021 Alternate RDP and VNC, reconnect with saved credentials, kill
  x11vnc, and prove one shared display plus stable Xorg/QMT/MCP identities.
- [x] T022 Run live MCP health/xtdata smoke and record redacted verification.
- [x] T023 Commit with Conventional Commits, open a credited PR, and observe
  PR CI to terminal success.
- [x] T024 Merge, observe main CI and automated release, deploy the released
  behavior safely to NAS, and verify rollback remains available.
- [x] T025 Reply to and close PR #19 as superseded, crediting adopted ideas and
  linking the released same-session implementation.
