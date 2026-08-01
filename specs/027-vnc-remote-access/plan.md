# Implementation Plan: VNC Remote Access

**Branch**: `codex/027-vnc-remote-access` | **Date**: 2026-08-01 |
**Spec**: `specs/027-vnc-remote-access/spec.md`

## Summary

Add an opt-in x11vnc adapter to the persistent Xorg desktop created by 026.
Preserve PR #19's raw-VNC client workflow, shared/reconnecting x11vnc behavior,
and usable XFCE desktop expectation, while eliminating its separate Xvfb stack,
duplicate-QMT `both` mode, argv password exposure, and wildcard publication.

## Technical Context

**Language/Version**: Bash, Dockerfile, Compose YAML, Markdown, Python 3.12 tests.

**Dependencies**: Existing xrdp 0.10.6.1/xorgxrdp 0.10.5 persistent display,
x11vnc, TigerVNC password utility, Docker Compose.

**State**: `/run/qmt/vnc/passwd` for ephemeral authentication and the existing
`/run/qmt/desktop/status.json` for lifecycle state.

**Target**: Native linux/amd64 appliance; standard VNC clients on desktop and
Android; RDP remains available.

**Constraints**: One display, one XFCE, one Wine prefix, one QMT, one MCP;
loopback by default; no secrets in argv/status/mcp.env; no noVNC.

## Constitution Check

- **I Broker-agnostic**: PASS. No broker artifact or client-specific code.
- **II Read-only default**: PASS. Remote human desktop behavior is unchanged;
  no MCP trading tool is added.
- **III Reproducible pinned builds**: PASS. Distribution packages are installed
  in the stable runtime dependency layer and verified in-image.
- **IV Contract-first MCP**: PASS. MCP tools and schemas are unchanged.
- **V Observable/readiness-gated**: PASS. VNC readiness is independent from MCP
  liveness and xtdata readiness.
- **VI Security by default**: PASS. VNC is opt-in, loopback-first,
  password-protected, redacted, and documented for tunnel/VPN use only.
- **VII Spec-driven delivery**: PASS. 027 is approved before implementation and
  explicitly supersedes the VNC conclusions in 026 research.

## Architecture

1. Base Compose and persistent RDP behavior remain unchanged.
2. `docker-compose.vnc.yml` opts the service into VNC and publishes only the
   loopback host port by default.
3. The entrypoint validates persistent mode, host-bind acknowledgement, and
   VNC secret source before services start.
4. The entrypoint sends the resolved password to `tigervncpasswd -f` on stdin,
   installs a mode-0600 runtime auth file, and unsets plaintext values.
5. After the persistent supervisor discovers the xrdp-owned display and
   Xauthority, it starts x11vnc as `wineuser` on container port 5900.
6. x11vnc reads the existing display only. It does not own XFCE, QMT, MCP, or
   the container lifecycle.
7. The supervisor restarts x11vnc with bounded backoff on failure and publishes
   VNC readiness in schema-version-2 desktop status.

## PR #19 Integration Review

Adopt:

- raw VNC for saved-credential and cross-platform/mobile workflows;
- x11vnc rather than noVNC/websockify;
- `-forever`, `-shared`, `-noxdamage`, and `-repeat` for reconnects and QMT UI;
- mandatory authentication and an explicit usable window-managed desktop;
- explicit VNC process supervision and troubleshooting documentation.

Replace:

- separate Xvfb/XFCE/QMT/MCP with attachment to the persistent display;
- `both` sessions with simultaneous protocols over one session;
- `x11vnc -storepasswd <secret>` argv input with stdin filter generation;
- always-published VNC with an opt-in loopback Compose override;
- VNC failure terminating the whole container with isolated adapter recovery;
- plaintext VNC secret copied into `mcp.env` with a runtime auth file only.

## Verification Strategy

- Static/unit: shell syntax and ShellCheck, password-source fixtures, redaction,
  mode/bind gates, x11vnc policy flags, status schema, restart logic.
- Compose/image: default has no VNC port; override has loopback 15900; exact
  packages and executable checks; no noVNC/websockify.
- Regression: all Python, Go, release-policy, actionlint, MCP modern/legacy
  conformance, and image build gates.
- Native NAS: build from exact branch, enable loopback VNC, authenticate with a
  real client through a tunnel, alternate RDP/VNC, kill x11vnc, compare process
  identities, and run health/xtdata smoke.
- Delivery: Conventional Commit PR, green PR CI, merge, green main CI,
  successful automated release, production rollout, and PR #19 response.

## Complexity Tracking

| Complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Second remote-display protocol | VNC saved credentials and mobile clients are the requested capability | Persistent RDP does not provide the author's client workflow |
| Same-display x11vnc adapter | Both protocols must never create duplicate QMT sessions | PR #19's separate Xvfb `both` mode knowingly permits a second QMT |
| Separate runtime auth file | VNC authentication is required without plaintext argv or config copies | `x11vnc -storepasswd <secret>` temporarily exposes the secret in process arguments |
| Opt-in Compose override | Existing deployments must not gain a new listener | Always publishing 5900 widens the attack surface even when unused |
