# Verification: VNC Remote Access

**Date**: 2026-08-01

**Target**: Native linux/amd64 NAS

**Result**: Implementation and native acceptance passed; PR delivery pending

No host address, account identifier, token, password, broker credential, or
desktop capture is recorded here.

## Image and Build

- Final candidate image ID:
  `sha256:ddd50f71d1b6de54303c7939f582aa2c5569d490a6aed2c8fd88975c23059699`.
- Runtime size/layers: 6,046,987,527 bytes / 28 layers.
- Exact Ubuntu Noble packages `x11vnc=0.9.16-10` and
  `tigervnc-tools=1.13.1+dfsg-2build2` were installed after the expensive
  Wine/Python layer.
- The final native rebuild completed in 13 seconds with the Wine, Python, xrdp,
  xorgxrdp, and VNC package layers cached. The final image gate passed exact
  versions, x11vnc policy support, source-tool absence, and the existing xrdp
  security checks.
- The image does not expose port 5900 in metadata. Only the explicit VNC
  Compose override publishes it, on host loopback port 15900 by default.

## Native Client Acceptance

- A real VNC snapshot client authenticated through host loopback twice with the
  same retained credential. Both connections returned the same 1440x900 QMT
  desktop, proving reconnect rather than a second session.
- A VNC control client entered the existing broker login screen and reached the
  QMT main window. The capture used to verify this was removed because desktop
  images can contain account information.
- A FreeRDP 3 client completed the graphics handshake and remained connected
  for 12 seconds. `xrdp-sesman` recorded a reconnect to display `:10`, not a new
  display.
- RDP and VNC tests preserved Xorg PID 216, QMT PID 372, MCP PID 387, and the
  same schema-version-2 desktop status. The container restart count remained
  zero.

## Failure Isolation

- Killing x11vnc changed only its PID, from 276 to 1726. Xorg, QMT, MCP, xrdp,
  and the container remained running with their original identities.
- A newly authenticated VNC client connected after the isolated restart and
  received the same desktop.
- The first restricted-capability deployment exposed a `chmod`/`chown` order
  bug while creating the auth file. The order was corrected and covered by a
  regression assertion; the production capability set remains the five
  capabilities from Spec 026 and does not add `FOWNER`.

## MCP and Security Acceptance

- `qmtctl health` passed after the manual broker login and reported xtdata
  `ready`.
- A real `qmtctl snapshot 510300.SH` call succeeded with a structured live
  quote response.
- The hardening audit reported zero failures. Expected warnings cover the
  compatibility environment-backed RDP password, VNC fallback, raw-VNC tunnel
  requirement, and the deployment-private MCP TLS boundary.
- The auth file was mode 0600 and exactly eight bytes after stdin filter
  generation. No plaintext VNC password appeared in x11vnc argv, desktop
  status, `mcp.env`, or logs.
- File transfer, remote commands, and clipboard exchange were disabled. Default
  and TLS Compose renderings publish no VNC port; the VNC rendering publishes
  exactly `127.0.0.1:15900`.

## Regression Gates

- Ruff lint and format: passed for 96 files.
- Python 3.12 unit tier: 230 passed and one PostgreSQL-only test skipped; 48
  integration tests were deselected.
- Official-SDK integration tier: 48 passed.
- Go test, vet, normal build, and conformance-driver build: passed.
- The selected stable MCP `2026-07-28` and legacy `2025-11-25` conformance
  matrix passed before the final appliance-only edits; PR CI repeats it from a
  clean checkout.
- Release-policy tests: 7 passed.
- actionlint 1.7.12, ShellCheck, Bash syntax, Compose JSON assertions, and
  `git diff --check`: passed.

## Rollout and Rollback

- The accepted VNC behavior is running in the isolated production Compose
  project with RDP and VNC bound to host loopback and MCP retaining its existing
  publication policy.
- The previous deployment directory, container fallback, and pre-027 image tag
  remain available for rollback.
- PR CI, main CI, automated release, released-image rollout, and the credited
  PR #19 response will be appended after delivery reaches terminal success.
