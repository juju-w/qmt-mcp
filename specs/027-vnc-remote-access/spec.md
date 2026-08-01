# Feature Specification: VNC Remote Access

**Feature Branch**: `codex/027-vnc-remote-access`

**Created**: 2026-08-01

**Status**: Approved for implementation

**Depends on**: 005 (supervision/readiness), 010 (deployment hardening), 011
(release delivery), and 026 (secure persistent desktop).

## Summary

Add raw VNC as a first-class, opt-in way to enter the QMT desktop. The feature
exists for operators whose VNC clients can retain credentials and provide
lightweight Android or other cross-platform access that their RDP workflow does
not provide conveniently.

RDP and VNC must expose the same persistent Xorg/XFCE desktop. Enabling VNC
must not create an Xvfb display, another XFCE session, a second QMT process, or
another MCP supervisor. Operators may use RDP, VNC, or both client protocols;
the one desktop and process identities remain unchanged.

This specification incorporates the useful product and operational ideas from
PR #19 while replacing its separate-session `both` mode and broad VNC
publication with the persistent, loopback-first security model delivered by
026. noVNC and browser access remain out of scope.

## User Scenarios & Testing

### User Story 1 - Reconnect from a convenient VNC client (Priority: P1)

An operator saves the appliance VNC credential in an approved desktop or
Android VNC client, opens the already-running QMT desktop with one action, and
handles a login prompt or quick diagnostic without typing Linux/RDP credentials
again.

**Independent Test**: Enable VNC on a persistent appliance, save the VNC
credential in a real client, connect, disconnect, and reconnect while verifying
the same desktop and QMT window remain visible.

**Acceptance Scenarios**:

1. **Given** a persistent QMT desktop with VNC enabled, **when** an authenticated
   VNC client connects, **then** it sees and controls the existing QMT desktop.
2. **Given** the client stores the VNC credential, **when** it reconnects,
   **then** the standard VNC login can complete without an RDP login flow.
3. **Given** QMT displays a broker login, captcha, agreement, or upgrade prompt,
   **when** the operator enters through VNC, **then** the interaction remains
   manual and no broker credential is stored by the appliance.

### User Story 2 - Switch between RDP and VNC without duplicating QMT (Priority: P1)

An operator may use a higher-performance RDP client at a desk and a lightweight
VNC client on mobile, with both protocols observing the same session.

**Independent Test**: Record display, Xorg, QMT, MCP, and supervisor identities;
attach and detach RDP and VNC in both orders; verify all identities and singleton
counts are preserved.

**Acceptance Scenarios**:

1. **Given** an RDP client is attached, **when** VNC connects, **then** both
   clients observe the same display rather than separate desktops.
2. **Given** either client disconnects, **when** the other remains or reconnects,
   **then** QMT, MCP, subscriptions, and the desktop continue running.
3. **Given** repeated concurrent connects, **when** process counts are audited,
   **then** exactly one Xorg, one QMT root, one MCP supervisor, and one serving
   MCP process exist.

### User Story 3 - Opt in without exposing a weak desktop (Priority: P1)

An operator can enable VNC deliberately while the default deployment continues
to expose no VNC listener.

**Independent Test**: Render default and VNC Compose configurations and run the
hardening audit against safe and unsafe fixtures.

**Acceptance Scenarios**:

1. **Given** the default deployment, **when** it starts, **then** no host VNC
   port is published and no x11vnc process runs.
2. **Given** VNC is enabled, **when** no valid password is available, **then**
   startup fails before a VNC listener is created.
3. **Given** the VNC override without LAN acknowledgement, **when** Compose is
   rendered, **then** VNC binds to host loopback only.
4. **Given** a non-loopback VNC bind, **when** explicit LAN/VPN acknowledgement
   is absent, **then** entrypoint and hardening checks fail closed.
5. **Given** raw VNC has no transport encryption, **when** documentation is
   followed, **then** remote access uses an SSH tunnel or trusted VPN and is
   never presented as internet-safe.

### User Story 4 - Diagnose VNC without destabilizing MCP (Priority: P2)

An operator can tell whether the desktop, MCP, and optional VNC adapter are
ready independently.

**Independent Test**: Kill x11vnc and verify bounded automatic restart plus
secret-free status while Xorg, QMT, MCP, and xrdp identities remain unchanged.

**Acceptance Scenarios**:

1. **Given** x11vnc exits, **when** the desktop supervisor observes it, **then**
   VNC is restarted with bounded backoff without restarting QMT or MCP.
2. **Given** VNC cannot recover, **when** status is inspected, **then** it reports
   VNC degraded while preserving the healthy persistent desktop and MCP.
3. **Given** logs, process arguments, status JSON, or `mcp.env` are inspected,
   **when** VNC is configured, **then** no VNC password appears.

## Functional Requirements

- **FR-001**: VNC MUST be disabled by default and enabled only by explicit
  configuration plus an explicit Compose override that publishes its port.
- **FR-002**: Enabled VNC MUST use raw RFB through x11vnc and MUST support normal
  VNC client credential persistence, including lightweight mobile clients.
- **FR-003**: Enabled VNC MUST require `QMT_DESKTOP_MODE=persistent` and attach
  to the persistent xrdp-managed Xorg display and Xauthority.
- **FR-004**: VNC MUST NOT create Xvfb, XFCE, QMT, Wine, or MCP processes beyond
  those already owned by the persistent desktop.
- **FR-005**: RDP and VNC attach/detach in any order MUST preserve the display,
  Xorg, QMT, MCP, and supervisor identities.
- **FR-006**: Default Compose MUST publish no VNC port; the VNC override MUST
  default to `127.0.0.1:${VNC_PORT:-15900}:5900`.
- **FR-007**: Non-loopback VNC publishing MUST require explicit
  `QMT_VNC_ALLOW_LAN=1`, produce a hardening warning, and remain unsupported on
  the public internet.
- **FR-008**: A VNC password MUST be provided by an owner-only regular secret
  file, a compatibility environment value, or an explicit fallback to the
  resolved RDP password, in that order.
- **FR-009**: The resolved VNC password MUST be at least eight characters,
  reject known defaults, and be converted to the VNC auth file through standard
  input rather than a command argument.
- **FR-010**: Documentation MUST state that classic VNC authentication uses
  only the first eight password characters and is not transport encryption.
- **FR-011**: The auth file MUST be ephemeral, owner-only, excluded from image
  layers and the broker pack, and referenced with x11vnc `-rfbauth`.
- **FR-012**: File transfer and remote-command features MUST be disabled;
  clipboard behavior MUST be explicit and disabled by default.
- **FR-013**: x11vnc MUST support persistent shared reconnects and the QMT UI's
  keyboard/repaint behavior without adding noVNC or websockify.
- **FR-014**: x11vnc failure MUST NOT terminate or recreate the persistent
  desktop, QMT, MCP, xrdp, or container; supervision MUST retry it with bounded
  backoff and expose degraded state after repeated failure.
- **FR-015**: Desktop status MUST atomically expose `vnc_enabled`, `vnc_ready`,
  and a VNC PID when present, without credentials or account information.
- **FR-016**: The image MUST verify x11vnc and the password-file utility are
  installed without adding a compiler or browser desktop stack.
- **FR-017**: Hardening checks and automated tests MUST cover disabled defaults,
  password sources and redaction, mode gating, bind gating, Compose publication,
  x11vnc flags, status, restart behavior, and the no-second-QMT invariant.
- **FR-018**: Native amd64 acceptance MUST include a real authenticated VNC
  client, RDP/VNC alternation, x11vnc restart, process identity checks, and a
  live MCP/xtdata smoke.
- **FR-019**: Existing MCP, OAuth, CLI, broker-pack, RDP, database, subscription,
  and read-only behavior MUST remain unchanged.
- **FR-020**: Delivery MUST credit PR #19 for the VNC workflow requirement and
  relevant x11vnc/XFCE operational input, while explaining why its separate
  display implementation is superseded.

## Non-Goals

- Browser/noVNC access, WebSocket proxying, or a public desktop endpoint.
- Automating QMT broker credentials, captcha, MFA, agreements, or trading.
- Replacing xrdp as the persistent desktop owner.
- Creating a separate VNC-only Xvfb/QMT session.
- Claiming VNC performance is equivalent to xrdp 0.10.

## Success Criteria

- A saved-credential VNC client can repeatedly enter the existing QMT desktop.
- RDP and VNC always show one shared desktop with one QMT and one MCP.
- Default deployments have no VNC publication or process.
- Unsafe password or network configurations fail before x11vnc listens.
- Killing x11vnc does not change Xorg/QMT/MCP identities and VNC recovers.
- Full repository CI, native image smoke, NAS acceptance, main CI, and the
  automated release all complete successfully.
