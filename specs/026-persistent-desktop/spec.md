# Feature Specification: Secure Persistent Desktop

**Feature Branch**: `codex/026-persistent-desktop`

**Created**: 2026-07-31

**Status**: Implemented and native-amd64 verified on 2026-08-01

**Depends on**: 001 (broker pack), 005 (supervision/readiness), 010
(deployment hardening), and 011 (release/image delivery).

## Summary

Make the existing xrdp/Xorg desktop start and survive independently of an
interactive RDP connection. In persistent mode, a container restart creates
exactly one XFCE desktop session, launches QMT and the MCP supervisor in that
session, and lets an operator later attach to the same desktop over RDP for
first login, reauthentication, upgrades, or fault recovery.

The feature keeps one remote-desktop protocol and one X session. It does not
add VNC, noVNC, or a parallel display stack. Broker credentials, captcha, user
agreements, and other QMT login interactions remain human-operated inside the
desktop.

The same delivery closes current RDP security gaps: an obsolete vulnerable
xrdp package, all-interface host publishing, a known default password, a baked
shared TLS key, classic-RDP fallback, unrestricted login users and channels,
and unnecessary sudo access from the desktop account.

## User Scenarios & Testing

### User Story 1 - Recover automatically after restart (Priority: P1)

An operator restarts the NAS, container, or appliance and gets one running
desktop, QMT terminal, and MCP service without first opening an RDP client.

**Independent Test**: Start a configured native linux/amd64 appliance in
persistent mode, never connect an RDP client, and verify one Xorg/XFCE session,
one QMT process tree, one MCP supervisor, and a live MCP endpoint.

**Acceptance Scenarios**:

1. **Given** a broker pack with reusable QMT login state, **when** the container
   starts, **then** one desktop session starts and MCP becomes live without an
   RDP connection.
2. **Given** QMT requires interactive login or confirmation, **when** the
   desktop starts, **then** it remains available for an operator and readiness
   reports the connector as unavailable without fabricating success.
3. **Given** the container is recreated ten times, **when** each generation
   becomes stable, **then** no generation contains duplicate Xorg, QMT, or MCP
   instances.
4. **Given** desktop bootstrap repeatedly fails, **when** the retry budget is
   exhausted, **then** the container fails visibly with a bounded reason and
   does not enter an unbounded restart storm.

---

### User Story 2 - Enter and leave the same desktop (Priority: P1)

An operator connects with a normal RDP client, sees the already-running QMT
desktop, performs any required interaction, and disconnects without stopping
QMT or MCP.

**Independent Test**: Record the display and process identities before an RDP
connection, connect and disconnect with Windows App or FreeRDP, then verify the
same display and processes remain alive and reconnectable.

**Acceptance Scenarios**:

1. **Given** the persistent desktop already exists, **when** the configured
   operator logs in, **then** xrdp reconnects that user to the existing Xorg
   display rather than creating another session.
2. **Given** the operator changes client resolution or reconnects from another
   approved client, **when** the RDP session resumes, **then** it remains the
   same logical desktop and does not launch a second QMT.
3. **Given** the operator disconnects without logging out, **when** no RDP
   client remains connected, **then** XFCE, QMT, quote subscriptions, and MCP
   continue running.
4. **Given** the operator explicitly logs out or the desktop crashes, **when**
   supervision observes the loss, **then** recovery creates at most one new
   session and records why the prior session ended.

---

### User Story 3 - Expose the trading desktop safely (Priority: P1)

An operator deploys the appliance without unintentionally exposing a weak or
vulnerable RDP service to the LAN or internet.

**Independent Test**: Run the deployment audit against safe and intentionally
unsafe fixtures, scan the resulting listener and TLS negotiation, and verify
that unsafe defaults fail before the service starts.

**Acceptance Scenarios**:

1. **Given** no bind address is configured, **when** Compose renders, **then**
   RDP is published on host loopback only, including no wildcard IPv6 listener.
2. **Given** a missing, empty, short, or known-default RDP password, **when**
   the appliance starts, **then** startup fails before xrdp listens.
3. **Given** a client that offers only classic RDP security, **when** it
   connects, **then** the server rejects it and requires TLS 1.2 or later.
4. **Given** two appliance instances, **when** their certificates are
   inspected, **then** each has a distinct persisted private key that was not
   present in an image layer.
5. **Given** an authenticated desktop user, **when** it inspects privileges and
   redirection channels, **then** it has no sudo access and cannot redirect
   client drives or files unless the operator explicitly enables that policy.
6. **Given** the bundled xrdp version is below the approved security floor,
   **when** the image gate runs, **then** the build fails.

---

### User Story 4 - Diagnose desktop and login state (Priority: P2)

An operator can distinguish desktop bootstrap failure, QMT login required,
xtdata not ready, MCP failure, and duplicate-session prevention without reading
raw process lists.

**Independent Test**: Inject each lifecycle failure into a test image and
verify bounded status files, health behavior, and secret-free logs.

**Acceptance Scenarios**:

1. **Given** desktop bootstrap is in progress, **when** health is inspected,
   **then** the current phase and elapsed time are visible without a secret.
2. **Given** MCP is live but xtdata is unavailable because QMT needs attention,
   **when** readiness is queried, **then** liveness remains distinct from QMT
   connector readiness.
3. **Given** a second session or QMT launch is attempted, **when** the singleton
   guard rejects it, **then** the existing instance remains untouched and an
   actionable event is logged.

---

### User Story 5 - Migrate without losing manual recovery (Priority: P2)

An existing operator can upgrade safely, opt into persistent startup, and
return to manual RDP-start behavior for diagnosis.

**Independent Test**: Upgrade a copy of an existing broker pack, exercise both
desktop modes, and roll back the image without changing broker data.

**Acceptance Scenarios**:

1. **Given** an existing deployment with no new mode configured, **when** it is
   upgraded, **then** the documented compatibility mode remains available.
2. **Given** persistent mode is enabled, **when** it passes the preflight,
   **then** the broker pack is reused without migrating or storing brokerage
   credentials outside QMT.
3. **Given** persistent startup cannot be recovered, **when** the operator
   selects manual mode and recreates the container, **then** normal RDP login
   can create the desktop for diagnosis.

## Edge Cases

- A stale xrdp session record exists but its Xorg or window manager is dead.
- Bootstrap races an operator RDP login during container startup.
- The RDP client requests a different color depth, resolution, or monitor set.
- QMT spawns a helper MiniQMT process and singleton detection must not kill it.
- QMT exits while MCP remains alive, or MCP exits while QMT remains alive.
- xrdp, xrdp-sesman, Xorg, XFCE, or the session bootstrap helper exits first.
- A certificate directory is missing, read-only, shared across instances, or
  contains permissions that expose the private key.
- A password file has a trailing newline, wrong owner/mode, or is replaced
  during startup.
- An RDP client repeatedly fails authentication or opens many TCP connections.
- Docker publishes only IPv4 loopback but unexpectedly publishes IPv6 wildcard.
- File, image, text clipboard, audio, and drive redirection policies differ.
- An abrupt host power loss leaves pidfiles, X sockets, or session locks.
- The broker login state expires while the desktop remains healthy.

## Requirements

### Functional Requirements

- **FR-001**: The appliance MUST retain xrdp with xorgxrdp/Xorg as its only
  interactive remote-desktop backend.
- **FR-002**: The appliance MUST NOT install or expose x11vnc, noVNC, or a
  second parallel graphical session as part of this feature.
- **FR-003**: The appliance MUST support explicit `manual` and `persistent`
  desktop startup modes with documented migration and rollback behavior.
- **FR-004**: Persistent mode MUST create one XFCE session before any RDP client
  connects and MUST launch the existing QMT and MCP autostarts in that session.
- **FR-005**: The persistent-session implementation MUST pass a native
  linux/amd64 proof that a later RDP login reattaches the same logical Xorg
  session. The POC is a blocking gate, not post-implementation evidence.
- **FR-006**: Session selection MUST be restricted to the configured desktop
  user and MUST reject or contain any path that would create a second QMT.
- **FR-007**: QMT and MCP startup MUST each have an atomic, stale-safe singleton
  guard scoped to the container instance.
- **FR-008**: Disconnecting an RDP client MUST NOT terminate the persistent
  desktop, QMT, MCP, or quote-subscription workers.
- **FR-009**: Brokerage login, captcha, agreements, and interactive upgrades
  MUST remain manual desktop operations; the appliance MUST NOT store or type
  brokerage credentials.
- **FR-010**: Desktop startup, recovery, and shutdown MUST be owned by a
  supervised process tree with bounded retries and graceful termination.
- **FR-011**: The image MUST pin an upstream-supported xrdp/xorgxrdp pair that
  contains all security fixes accepted at implementation time. The initial
  research floor is xrdp 0.10.6.1 and xorgxrdp 0.10.5.
- **FR-012**: The image gate MUST report exact xrdp/xorgxrdp versions and fail
  if they differ from the pinned approved versions.
- **FR-013**: xrdp MUST enforce TLS security with TLS 1.2 or later and MUST NOT
  negotiate classic RDP security.
- **FR-014**: Every appliance instance MUST use a unique private key generated
  at runtime into persistent instance storage or mounted by the operator. No
  RDP private key may be inherited from or baked into a public image layer.
- **FR-015**: RDP host publishing MUST default to loopback. Wildcard/LAN binding
  MUST require an explicit opt-in acknowledged by the hardening check, and
  public-internet RDP MUST remain unsupported.
- **FR-016**: Startup MUST reject an absent, empty, known-default, or otherwise
  policy-invalid desktop password before opening the listener.
- **FR-017**: File-backed desktop secrets MUST be supported and preferred. A
  bootstrap password MUST be delivered through a file descriptor and MUST NOT
  appear in process arguments, generated config, logs, or image layers.
- **FR-018**: The desktop account MUST not belong to sudo/admin groups, root RDP
  login MUST be disabled, and only an explicit terminal-server group MUST be
  permitted to authenticate.
- **FR-019**: Client drive and file redirection MUST be disabled by default.
  Text clipboard, image clipboard, audio, and other dynamic channels MUST have
  explicit least-privilege policy controls.
- **FR-020**: Session count and authentication behavior MUST be bounded, and
  the deployment guide MUST require a VPN, SSH tunnel, or network allowlist
  rather than treating application authentication as an internet perimeter.
- **FR-021**: Container hardening MUST test `no-new-privileges`, required Linux
  capabilities, writable paths, and non-root desktop operation, retaining only
  privileges proven necessary for xrdp-sesman and Xorg startup.
- **FR-022**: Health and logs MUST distinguish desktop bootstrap, desktop ready,
  QMT attention required, xtdata readiness, MCP liveness, retry exhaustion, and
  duplicate suppression without exposing credentials or account data.
- **FR-023**: The existing deployment preflight MUST become an enforceable
  desktop audit covering bind address, wildcard IPv6, password source, TLS-only
  mode, unique certificate, package floor, sudo/group policy, channel policy,
  and active session/process counts.
- **FR-024**: Base Compose, hardened Compose, examples, deployment docs,
  `AGENT.md`, and the operations skill MUST describe one consistent desktop and
  network model without duplicating stale service definitions.
- **FR-025**: Automated tests MUST cover configuration validation, secret
  redaction, singleton races, stale state, bounded retry, signal handling,
  version gates, TLS settings, and unsafe deployment fixtures.
- **FR-026**: Native amd64 acceptance MUST cover cold start without a client,
  Windows App or FreeRDP attach/detach/reattach, resolution change, QMT manual
  login path, ten container restarts, and manual-mode rollback.
- **FR-027**: Performance evidence MUST compare the current xrdp 0.9 path with
  the selected xrdp 0.10 GFX codec policy on the same host and client; a change
  that materially regresses interactive QMT use MUST not ship.
- **FR-028**: Existing broker-pack, MCP auth, read-only, OAuth, database,
  subscription, and CLI behavior MUST remain unchanged.

## Key Entities

- **Desktop Startup Mode**: Manual or persistent ownership of the one allowed
  XFCE/Xorg desktop.
- **Desktop Session Identity**: Generation, user, X display, session ID,
  process identities, and lifecycle timestamps for one logical desktop.
- **Remote Access Policy**: Host bind, TLS mode, certificate identity, allowed
  user group, channel restrictions, and session bounds.
- **Desktop Secret Source**: File-backed or compatibility environment input
  used for PAM authentication without persisting the value elsewhere.
- **Desktop Lifecycle State**: Starting, desktop-ready, QMT-attention-required,
  connector-ready, degraded, retrying, or failed.
- **Singleton Lease**: Atomic ownership record preventing duplicate QMT or MCP
  launches within one appliance instance.

## Success Criteria

- **SC-001**: Persistent mode reaches one desktop plus live MCP within 120
  seconds of container start without an RDP client when QMT state is reusable.
- **SC-002**: Across ten forced recreates, every stable generation has exactly
  one Xorg desktop, one QMT terminal tree, and one MCP supervisor.
- **SC-003**: Attach, disconnect, and reattach preserve the same display and QMT
  process identity, including one supported resolution change.
- **SC-004**: Default Compose publishes no RDP listener beyond host loopback and
  has no known default password.
- **SC-005**: TLS scanning accepts only TLS 1.2 or later, rejects classic RDP
  security, and observes a per-instance certificate not found in the image.
- **SC-006**: Unsafe password, wildcard exposure, obsolete xrdp, shared key,
  sudo-enabled desktop user, or forbidden channel fixtures all fail an
  automated gate.
- **SC-007**: RDP disconnect leaves QMT, MCP, and quote subscriptions running for
  at least 30 minutes with no connected desktop client.
- **SC-008**: Native testing shows no material regression in QMT interaction;
  the selected xrdp 0.10 codec records equal or lower bandwidth and acceptable
  host CPU compared with the existing path.
- **SC-009**: No test log, process list, generated env file, image history, or
  committed file contains the desktop password or brokerage credentials.

## Assumptions

- The target remains native linux/amd64; Apple Silicon emulation is not an
  acceptance environment for Wine/QMT.
- QMT may persist its own login state in the read-write broker pack, but the
  appliance cannot guarantee that a broker will permit unattended re-login.
- Operators can use Windows App, FreeRDP, an SSH tunnel, or a VPN.
- A desktop session may remain disconnected indefinitely, but it must still be
  bounded to one session for the configured user.

## Out of Scope

- Automating brokerage credentials, captcha, MFA, agreements, or upgrades.
- Public internet RDP, browser desktop access, VNC, or multi-user desktops.
- Running two QMT terminals against one Wine prefix or broker pack.
- Replacing the MCP authentication or authorization model.
