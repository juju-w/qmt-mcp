# Verification: Secure Persistent Desktop

**Date**: 2026-08-01

**Target**: Native linux/amd64 NAS

**Result**: Core implementation and production rollout passed

No host address, account identifier, token, password, or broker credential is
recorded here.

## Image and Build

- Final image ID: `sha256:9147fdd529681277a3854dd5fbc0c87b7fca39b76e4e906b3b097560698021bc`
- Runtime size/layers: 6,017,495,311 bytes / 26 layers.
- xrdp 0.10.6.1 and xorgxrdp 0.10.5 were built from checksum-pinned upstream
  archives. The final image contains no compiler, source tree, distro xrdp
  package metadata, or pre-generated TLS private key.
- The Dockerfile image gate passed exact versions, module/config presence,
  source-tool absence, login policy, channel policy, and key absence.
- A no-op native rebuild after separating xrdp, Wine/Python, and application
  layers completed in 5.11 seconds with the expensive layers cached.

## Native Session Acceptance

- Persistent cold boot reached one `Xorg :10`, one QMT root, and one MCP in
  about eight seconds without an RDP client.
- FreeRDP TLS attach/disconnect/reattach preserved the same display and process
  identities at 1280x800 and 1600x900. A classic-RDP-only connection failed;
  TLS authentication succeeded.
- After more than 30 disconnected minutes, Xorg PID 205, QMT PID 3099, and MCP
  PID 375 were unchanged; Docker reported healthy with zero restarts and xtdata
  remained ready.
- Ten forced recreate generations each reached ready in about eight seconds
  with exactly one Xorg, one QMT root, one MCP, one xrdp, and one sesman. Every
  generation had zero restarts, a stable persisted certificate, and a clean
  exit code 0 in about three seconds.
- Manual rollback started xrdp as PID 1 with zero Xorg/QMT/MCP processes. A
  real FreeRDP TLS login then created exactly one of each and MCP became live.

## Security Acceptance

- RDP publishes on host loopback only; TLS 1.2/1.3 is required.
- Each instance receives a persisted unique certificate. Private keys are
  `0640 root:xrdp`; the desktop user has no sudo access.
- Drive, clipboard, audio, RemoteApp, and video channels are disabled by
  default; the dynamic channel remains for resolution changes.
- `no-new-privileges` is active. `cap-drop=ALL` succeeds with only `CHOWN`,
  `DAC_OVERRIDE`, `KILL`, `SETGID`, and `SETUID`. Removing `DAC_OVERRIDE`
  failed the real broker write preflight; removing `FOWNER` still passed.

## Regression Gates

- Python: 273 passed, 1 skipped. The skip is the external PostgreSQL tier
  because `QMT_TEST_DB_URL` was not configured.
- Go: test, vet, build, and MCP conformance passed.
- qmtctl: linux, macOS, and Windows builds passed for amd64 and arm64.
- Release-policy scripts: 7 passed.
- Ruff lint/format, actionlint, shell syntax, ShellCheck, Compose JSON security
  assertions, and `git diff --check` passed.

## Production Rollout

- The final image was deployed from an isolated persistent Compose directory.
- The previous production container and image were retained under a rollback
  name/tag.
- Production reports healthy with zero restarts, one persistent Xorg/QMT/MCP
  session, loopback-only RDP, the five-capability policy, and an independent
  certificate.
- Manual QMT login completed over TLS RDP. `qmt_health` reported logged-in and
  xtdata ready, and a real `qmt_xtdata_snapshot` call for `510500.SH` succeeded.
- The isolated production Compose project was attached to the existing external
  PostgreSQL network with a deployment-private override. After restarting only
  the supervised MCP child, health reported `database=connected` with the
  `marketdata` domain while the Xorg and QMT process identities stayed intact.

## Merge and Release

- PR #20 merged as `7a9c667b5f5dd3c616b69e0424928650143b57d8` after all six
  PR checks passed. Main CI run `30652768718` then completed all six jobs,
  including the native appliance build and Compose security assertions.
- Automated release run `30653489470` completed successfully and published
  `v0.12.0`, six qmtctl archives for Windows, macOS, and Linux on amd64/arm64,
  `SHA256SUMS`, and the linux/amd64 GHCR appliance manifest
  `sha256:1b7c7ae72abe0b96beaefea9c16c7f6c73c9759e605892e03f9cf0b97ed90578`.
- Production remains on the functionally accepted native image rather than a
  cosmetic retag: the NAS-to-GHCR path repeatedly timed out on the 827 MiB Wine
  prefix blob at about 0.12 MiB/s. The running image contains the released
  desktop behavior, is healthy with zero restarts, and passed a fresh qmtctl
  snapshot after the release.

## Residual Evidence

- T012 remains open: run a controlled xrdp 0.9 versus 0.10 CPU/bandwidth
  benchmark on the same host and client. Real QMT login, window interaction,
  disconnect, reconnect, and resize showed no observed usability regression.
- T008-T010 retain optional stub, macOS-client recording, and fault-injection
  coverage beyond the completed real-broker FreeRDP acceptance.
- T039 retains broader unit-level race, stale-state, and abrupt-kill fault
  injection beyond the completed native lifecycle and unsafe-fixture gates.
