# Tasks: Secure Persistent Desktop

## Phase 1 - Specification and production audit

- [x] T001 Record the persistent desktop, same-session access, security,
  observability, and migration requirements in `spec.md`.
- [x] T002 Capture a redacted read-only NAS baseline for listeners, process
  state, xrdp versions/configuration, certificate, privileges, and channels in
  `research.md`.
- [x] T003 Record upstream xrdp security/version/session evidence and evaluate
  xrdp, headless, VNC, dual-stack, and loopback-client alternatives.
- [x] T004 Define desktop lifecycle entities and the configuration/session/TLS/
  audit contract.
- [x] T005 Complete the constitution check, implementation plan, quickstart,
  and requirements checklist.

## Phase 2 - Blocking native POC

- [x] T006 Create a disposable native amd64 POC image with pinned official
  xrdp 0.10.6.1 and xorgxrdp 0.10.5 sources and verified SHA-256 values.
- [x] T007 Start xrdp-sesman/xrdp and use `xrdp-sesrun -F 0` to create an XFCE
  session without exposing the password in argv, logs, or generated files.
- [ ] T008 Verify XFCE autostart semantics with harmless QMT/MCP stubs before
  using a real broker pack.
- [ ] T009 Attach, disconnect, and reattach FreeRDP and macOS Windows App while
  recording session ID, display, Xorg, XFCE, QMT-stub, and MCP-stub identities.
- [ ] T010 Test resolution/color-depth changes, startup login races, logout,
  crash, abrupt container kill, stale files, and five restart generations.
- [x] T011 Test a real broker pack on native amd64, complete QMT login manually,
  recreate the container, and determine which broker-login state is reusable.
- [ ] T012 Benchmark xrdp 0.9 versus 0.10 GFX RFX/H.264 policies for host CPU,
  bandwidth, window movement, text input, and QMT usability.
- [x] T013 Record POC evidence and either approve the xrdp-sesrun architecture
  or stop and revise `research.md`, `plan.md`, and the contract.

## Phase 3 - Patched and hardened RDP foundation

- [x] T014 Add a checksum-pinned multi-stage xrdp/xorgxrdp build to
  `appliance/Dockerfile` without compilers or source in the final image.
- [x] T015 Add image gates for exact versions, xorgxrdp module loading, TLS
  support, and selected GFX codec support.
- [x] T016 Add project-owned `appliance/config/xrdp/xrdp.ini` enforcing TLS
  1.2/1.3, no classic RDP fallback, bounded listeners, and restricted channels.
- [x] T017 Add project-owned `appliance/config/xrdp/sesman.ini` disabling root
  login, enforcing a dedicated login group, one-user session policy, and
  least-privilege clipboard/drive behavior.
- [x] T018 Set `USER_SUDO=no`, remove `wineuser` from admin groups, and test the
  minimum container capabilities plus `no-new-privileges` compatibility.
- [x] T019 Add per-instance generated or mounted RDP certificates with strict
  permissions, persistence, expiry/fingerprint diagnostics, and no image key.

## Phase 4 - Persistent desktop lifecycle (US1)

- [x] T020 [US1] Add fail-closed desktop config and password-file resolution to
  `appliance/scripts/qmt-entrypoint.sh`.
- [x] T021 [US1] Implement the persistent desktop supervisor with local sesman wait,
  `-F 0` authentication, exclusive desktop lease, session discovery, and
  bounded retry.
- [x] T022 [US1] Arrange PID 1/subreaping and graceful signal ownership based on
  POC evidence; avoid an unneeded general process manager.
- [x] T023 [US1] Add stale-safe kernel singleton locks to `start-qmt.sh` and
  `qmt-supervisor.sh` while allowing legitimate QMT helper children.
- [x] T024 [US1] Add desktop health integration and atomic secret-free runtime
  status for bootstrap, desktop, QMT attention, connector, MCP, and failure.
- [x] T025 [US1] Preserve explicit `manual` mode and verify rollback against the
  same broker pack.

## Phase 5 - Same-session operator access (US2)

- [x] T026 [US2] Configure rejoin policy and deterministic user/color-depth
  behavior so an RDP login selects the pre-created display.
- [x] T027 [US2] Reject a second desktop/QMT attempt without disturbing the
  established session and log a stable reason code.
- [x] T028 [US2] Verify RDP disconnect keeps QMT, MCP, and subscriptions alive
  for at least 30 minutes.
- [x] T029 [US2] Verify resolution change and reconnect from approved clients
  preserve the session and process identities.

## Phase 6 - Secure deployment boundary (US3)

- [x] T030 [US3] Change base Compose and `.env.example` to loopback RDP binding,
  no default password, file-backed secret support, and instance certificate
  storage.
- [x] T031 [US3] Make wildcard/LAN publishing require explicit acknowledgement
  and ensure IPv6 cannot silently widen a loopback request.
- [x] T032 [US3] Refactor `docker-compose.tls.yml` into a non-duplicating
  override/shared model so new feature environment does not drift.
- [x] T033 [US3] Extend `harden-check.sh` or add a desktop audit for package
  floor, TLS, certificate uniqueness, bind, password source, login group, sudo,
  channels, capabilities, and process/session count.
- [x] T034 [US3] Add unsafe fixtures proving default password, wildcard bind,
  obsolete xrdp, shared key, sudo, classic RDP, and drive/file channels fail.

## Phase 7 - Observability and migration (US4/US5)

- [x] T035 [US4] Integrate desktop lifecycle with Docker health and existing
  MCP liveness/readiness without claiming xtdata readiness before QMT login.
- [x] T036 [US4] Add bounded, redacted logs and diagnostics for every lifecycle
  state and duplicate/retry outcome.
- [x] T037 [US5] Add migration warnings for compatibility password input,
  manual/persistent mode selection, secure bind changes, and rollback.
- [x] T038 [US5] Update appliance/root README, deployment docs, `AGENT.md`, and
  `skills/qmt-mcp-ops/SKILL.md` with the one-session model and safe access flow.

## Phase 8 - Verification and delivery

- [ ] T039 Add shell/unit tests for config, secret resolution, singleton races,
  stale state, retries, status JSON, signal handling, and redaction.
- [x] T040 Add container tests for versions, TLS scan, unique certificates,
  group/sudo/channels, host bind render, and unsafe fixtures.
- [x] T041 Run native cold boot, real QMT login, attach/detach/reattach,
  resolution, 30-minute disconnect, and ten-recreate acceptance.
- [x] T042 Run all existing Python, Go, conformance, release-policy, actionlint,
  Compose, secret-scan, image-smoke, and cross-build gates.
- [x] T043 Record evidence in `VERIFICATION.md`, update the checklist, and open
  a Conventional Commit PR without merging PR #19 wholesale.
- [x] T044 After approval, merge only with green PR CI, observe main CI and the
  automated release to terminal success, then roll out to NAS with a backup and
  verify the hardened listener and persistent session.

## Dependencies

- T006-T013 are a hard gate for every implementation task.
- T014-T019 provide the secure xrdp foundation for persistent lifecycle.
- T020-T025 must complete before same-session and deployment acceptance.
- T030-T034 may proceed alongside lifecycle code after the POC, but release
  requires both lifecycle and security stories.
- T043/T044 require all selected implementation and verification tasks.
