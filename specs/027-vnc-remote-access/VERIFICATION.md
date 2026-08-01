# Verification: VNC Remote Access

**Date**: 2026-08-01

**Target**: Native linux/amd64 NAS

**Result**: Passed and released as v0.13.0

No host address, account identifier, token, password, broker credential, or
desktop capture is recorded here.

## Image and Build

- Final candidate image ID:
  `sha256:a48f323aa0193a0de4d0909c4fed0e11c0380484d129543d15eee78f3f20dca8`.
- GitHub Actions published `ghcr.io/juju-w/qmt-mcp:0.13.0` and `latest` with
  multi-architecture manifest digest
  `sha256:33134dbf9079c8d07552fe22b4b27d28f38d1e7817f8e5dc356e4870939e171b`.
- Runtime size/layers: 6,046,987,745 bytes / 28 layers.
- Exact Ubuntu Noble packages `x11vnc=0.9.16-10` and
  `tigervnc-tools=1.13.1+dfsg-2build2` were installed after the expensive
  Wine/Python layer.
- The review-fix native rebuild completed in 25 seconds with the Wine, Python,
  xrdp, xorgxrdp, and VNC package layers cached. The final image gate passed
  exact versions, x11vnc policy support, source-tool absence, and the existing
  xrdp security checks.
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
- The post-release production recreation authenticated through VNC at 1440x900
  and reported one ready persistent display `:10`, one QMT, one MCP, and zero
  container restarts.

## Failure Isolation

- Killing x11vnc changed only its PID, from 276 to 1726. Xorg, QMT, MCP, xrdp,
  and the container remained running with their original identities.
- Automated review found that the first implementation restarted a previously
  healthy adapter at the monitor interval. The corrected lifecycle first
  publishes degraded state and waits the configured restart backoff; the
  behavior test requires at least 1.8 seconds for a two-second setting.
- The released behavior was fault-injected on the production NAS. Killing
  x11vnc changed PID 259 to 2850; recovery took 2,985 ms after degraded state
  was observed with a two-second backoff. Xorg PID 219, QMT PID 1471, MCP PID
  403, and container restart count zero were unchanged.
- A newly authenticated VNC client connected after the isolated restart and
  received the same desktop.
- The first restricted-capability deployment exposed a `chmod`/`chown` order
  bug while creating the auth file. The order was corrected and covered by a
  regression assertion; the production capability set remains the five
  capabilities from Spec 026 and does not add `FOWNER`.

## MCP and Security Acceptance

- `qmtctl health` passed after the manual broker login and reported MCP ready,
  PostgreSQL connected, QMT logged in, and xtdata `ready`.
- A real `qmtctl snapshot --live 510300.SH` call returned a non-null five-level
  quote from `get_full_tick`, not the cache fallback.
- The hardening audit reported zero failures. Expected warnings cover the
  compatibility environment-backed RDP password, VNC fallback, raw-VNC tunnel
  requirement, and the deployment-private MCP TLS boundary.
- The auth file was mode 0600 and exactly eight bytes after stdin filter
  generation. No plaintext VNC password appeared in x11vnc argv, desktop
  status, `mcp.env`, or logs.
- Password validation rejects case-insensitive `password`, `changeme`, and
  `12345678` effective prefixes even when the caller appends ignored suffixes.
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
- PR #22 CI run `30687293131` passed all six jobs. Its first main run
  `30687461284` was intentionally cancelled before release when automated
  review found two P2 issues.
- PR #23 CI run `30687661484` passed all six jobs after the password-prefix and
  runtime-backoff fixes. A new Codex review reported no major issues.
- Main CI run `30687802834` passed all six jobs. Automated release run
  `30687911545` completed resolve/tag, GHCR publication, six qmtctl platform
  builds, checksums, and the GitHub Release.

## Rollout and Rollback

- The accepted VNC behavior is running in the isolated production Compose
  project with RDP and VNC bound to host loopback and MCP retaining its existing
  publication policy.
- PR #22 merged as `0cc21577d0d094209faf76a59f719d368f91a73e`; PR #23 merged
  as `7e9a1d7d30fc96bc21e16f411b06fdac04cd967c`. The automated release commit
  is `c3ffa1df0c1f4196dcdfe918817225d81683209b`.
- Release [v0.13.0](https://github.com/juju-w/qmt-mcp/releases/tag/v0.13.0)
  contains darwin, linux, and windows qmtctl artifacts for amd64 and arm64 plus
  `SHA256SUMS`.
- The NAS could not complete its direct GHCR pull because two incremental
  layers repeatedly timed out. Production therefore uses the native amd64
  image built from the released fix commit and independently passed through the
  same image gate; the public release manifest remains available for normal
  deployments.
- The prior production image is tagged `rollback-pre-v0.13.0`, and the pre-027
  deployment directory and image tag also remain available.
- PR #19 received a credited delivery reply linking #22, #23, and v0.13.0, then
  closed as superseded by the released same-session implementation.
