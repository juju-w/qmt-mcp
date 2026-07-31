# Research: Secure Persistent Desktop

**Date**: 2026-07-31

## Decision

Proceed with one patched xrdp/xorgxrdp stack. The native amd64 POC proved that
`xrdp-sesrun -F 0` pre-creates the same Xorg session an operator later
reattaches to, without exposing the password in argv or creating a second QMT.

Do not merge PR #19 as implemented. Its useful requirement is unattended
desktop startup; VNC, a second display protocol, and the `both` mode are not
required to meet that requirement.

## Native POC Outcome

The blocking POC and production acceptance completed on the native NAS:

- pinned xrdp 0.10.6.1 and xorgxrdp 0.10.5 built from verified upstream
  archives and passed the in-image gate;
- `xrdp-sesrun -F 0` created display `:10` before a client connected;
- FreeRDP TLS attach, disconnect, reattach, and 1280x800 to 1600x900 resize
  preserved the Xorg, QMT, MCP, and supervisor process identities;
- classic RDP security was rejected while TLS authentication succeeded;
- a disconnected, logged-in real QMT session remained ready for more than 30
  minutes with zero container restarts;
- ten forced container generations each reached ready in about eight seconds
  with one Xorg, one QMT root, one MCP, one xrdp, and one sesman process;
- manual mode created no desktop until a real TLS RDP login, then launched one
  desktop, QMT, and MCP as the rollback design requires;
- `cap-drop=ALL` works with only `CHOWN`, `DAC_OVERRIDE`, `KILL`, `SETGID`, and
  `SETUID`. Removing `DAC_OVERRIDE` correctly failed against the real host-owned
  broker pack; removing `FOWNER` did not affect startup or clean shutdown.

## Production Baseline Observed

The following facts were collected read-only from the actual NAS deployment on
2026-07-31. No address, account identifier, or secret value is recorded.

- The appliance container had been up for 10 days and was `unhealthy`.
- Only xrdp and xrdp-sesman were running. There was no Xorg desktop, QMT, or MCP
  process because no operator had created an RDP session after restart.
- Host ports 13389/RDP and 18765/MCP were published on IPv4 `0.0.0.0` and IPv6
  `[::]`.
- The host input/forward policy accepted traffic and the Docker user chain had
  no RDP/MCP restriction. The service was therefore reachable across the LAN,
  not protected by a host allowlist.
- The installed packages were xrdp `0.9.24-4` and xorgxrdp `0.9.19-1`.
- `security_layer=negotiate`, `crypt_level=high`, and TLS 1.2/1.3 were enabled,
  but classic RDP security remained negotiable.
- A client-side RDP Negotiation Request confirmed the runtime behavior:
  classic RDP was selected as protocol `0`, TLS was selected as protocol `1`,
  and a Hybrid/NLA-only request fell back to classic protocol `0`.
- The certificate was the inherited self-signed `ssl-cert-snakeoil` certificate
  with `CN=localhost`. Its private key is part of the reusable base-image
  filesystem rather than unique per deployment.
- The configured RDP password was the documented development default.
- `AllowRootLogin=true`, `AlwaysGroupCheck=false`, and `MaxSessions=50`.
- The desktop user belonged to the `sudo` group.
- Drive, dynamic virtual, clipboard, audio, RAIL, video, and utility channels
  were enabled. Clipboard restrictions were `none` in both directions.
- The existing `harden-check.sh` correctly failed the default password and
  warned about LAN/plain-HTTP exposure, but these findings did not prevent the
  running deployment.

## Current RDP Risk Review

| Priority | Finding | Impact | Required response |
|---|---|---|---|
| Critical | xrdp 0.9.24 permits unlimited login attempts despite `MaxLoginRetry=4` | The known default password is brute-forceable and the setting gives false assurance | Upgrade to xrdp 0.10.x and keep RDP behind loopback/VPN/firewall |
| Critical | xrdp 0.9.24 predates the fix for CVE-2025-68670 | Unauthenticated network input can cause a stack overflow with possible code execution | Pin a fixed upstream release; do not rely on Noble universe packages |
| Critical | RDP is LAN-wide with the known `qmt` password and no host filter | Any LAN peer can enter the live brokerage desktop | Remove the default, rotate immediately, default to loopback |
| High | Runtime negotiation accepts classic RDP and downgrades a Hybrid/NLA request to it | Classic security has weaker integrity guarantees; CVE-2026-32105 is avoided by enforcing TLS | Set `security_layer=tls` and TLS 1.2+ only; test negotiation from outside the container |
| High | The inherited snakeoil private key is reusable across image instances | Encryption has no trustworthy per-instance server identity and a public image can disclose the key | Generate or mount a unique persisted certificate at runtime |
| High | `wineuser` has sudo and a known password | Desktop compromise becomes root inside the container and gains full broker-pack access | Set `USER_SUDO=no`; restrict login group; disable root login |
| Medium | Drive/file/clipboard channels are broadly enabled | Authenticated-client compromise or operator error can import or exfiltrate files/data | Disable drives/files by default; make text clipboard explicit |
| Medium | `MaxSessions=50`, no group enforcement, and no idle bounds | Repeated sessions can consume memory or launch duplicate terminals | One-user/one-session policy, singleton locks, bounded retries |
| Medium | MCP is also plain HTTP on all LAN interfaces | Static bearer traffic can be observed by a hostile LAN peer | Keep MCP behind TLS or a controlled private network; retain OAuth/static auth |

## Version Research

- Ubuntu 24.04 Noble publishes xrdp `0.9.24-4` in `universe`.
- Ubuntu's fix for CVE-2025-68670 and CVE-2024-39917 is an ESM Apps package,
  not the public package installed in the appliance.
- Upstream xrdp `0.10.6.1`, released 2026-07-07, is the latest stable release at
  research time and fixes ten additional vulnerabilities plus a TLS regression.
- Upstream xorgxrdp `0.10.5`, released 2026-01-28, is the latest stable release
  at research time.
- xrdp 0.10 adds the GFX pipeline and reports higher frame rates and lower
  bandwidth than 0.9, especially with Windows 11 and Microsoft Remote Desktop
  for macOS. xrdp 0.10.2 adds H.264, but CPU-only hosts may perform better with
  RFX; the codec must be measured on this NAS rather than selected by name.

## Source Evidence

- xrdp security advisory for unlimited attempts (affected <=0.9.26):
  https://github.com/neutrinolabs/xrdp/security/advisories/GHSA-7w22-h4w7-8j5j
- Ubuntu CVE-2025-68670 status and ESM-only Noble fix:
  https://ubuntu.com/security/CVE-2025-68670
- Ubuntu CVE-2026-32105 and TLS-only mitigation:
  https://ubuntu.com/security/CVE-2026-32105
- xrdp 0.10.6.1 release:
  https://github.com/neutrinolabs/xrdp/releases/tag/v0.10.6.1
- xorgxrdp 0.10.5 release:
  https://github.com/neutrinolabs/xorgxrdp/releases/tag/v0.10.5
- xrdp project capabilities, TLS, and existing-session reconnect:
  https://github.com/neutrinolabs/xrdp
- xrdp 0.10 GFX performance notes:
  https://github.com/neutrinolabs/xrdp/discussions/3070
- `xrdp-sesrun` secure file-descriptor password input:
  https://manpages.debian.org/bookworm/xrdp/xrdp-sesrun.8.en.html

## Session Lifecycle Findings

There are two different logins:

1. The Linux/xrdp login authenticates `wineuser` and creates or reconnects an
   Xorg/XFCE session.
2. QMT performs its own broker login inside that desktop. QMT may reuse state
   from the broker pack, but captcha, MFA, agreements, expiry, and upgrades can
   still require a human.

Persistent startup can automate the first layer without automating the second.
The desktop can exist before QMT is authenticated, allowing an operator to
attach and finish the QMT interaction.

Current `sesman.ini` uses `Policy=Default`, which selects sessions by user and
bits-per-pixel and keeps disconnected sessions alive. In theory this permits:

1. Start xrdp-sesman and xrdp.
2. Feed the desktop password over file descriptor 0 to `xrdp-sesrun -F 0`.
3. Let the normal XFCE autostart launch QMT and MCP.
4. Reconnect the same user from Windows App to the existing display.

The implementation cannot assume this works under resolution, color-depth,
race, and disconnect conditions. The POC must prove all of them and capture
the session/process IDs.

## Alternatives

### A. Patched xrdp plus `xrdp-sesrun` bootstrap - Preferred hypothesis

Benefits:

- One RDP/Xorg desktop and one QMT.
- Operator attaches to the actual running application.
- No VNC listener, package, password format, or second transport.
- xrdp 0.10 may improve both security and performance.

Risks:

- `xrdp-sesrun` is documented primarily as a test/session-launch tool.
- Reattachment behavior must be proven with the actual macOS client.
- PID 1 ownership, signal handling, and stale session recovery need design.

### B. Xvfb-only headless mode - Rejected as the complete solution

It starts QMT/MCP automatically but does not let xrdp attach to the Xvfb
desktop. An operator would need a mode switch and restart for every QMT prompt.
It remains useful only as a diagnostic fallback, not the primary requirement.

### C. x11vnc over Xvfb - Rejected

It exposes the running desktop, but adds a second remote protocol, weaker
default security, framebuffer polling, another password surface, more image
content, and lower interactive performance. PR #19 also publishes VNC broadly
and offers a `both` mode that knowingly permits a second QMT session.

### D. xrdp and VNC together - Rejected

Separate X sessions make singleton behavior harder and can run multiple QMT
terminals against the same Wine prefix and broker pack.

### E. Synthetic FreeRDP client connected to loopback - Fallback spike only

A local client could create an xrdp session and disconnect, but it adds a full
client stack and more moving parts merely to invoke behavior sesman already
exposes. Consider only if `xrdp-sesrun` cannot produce a reconnectable session.

## Build Decision

Do not rely on the weekly base-image rebuild to upgrade xrdp. Ubuntu Noble's
public package remains obsolete. Build the pinned official xrdp and xorgxrdp
sources in a dedicated Docker build stage, verify source hashes, copy/install
only runtime artifacts, and assert versions during the image smoke.

The currently pinned Wine base must remain date-stamped. A deliberate base bump
may be evaluated separately, but it does not replace the xrdp version gate.

## Resolved Questions and Residual Work

The session, reattachment, resolution, PID 1, XFCE autostart, broker-state, and
Linux capability questions all passed on native amd64. QMT preserves its saved
account/password selection but can still present its normal manual login
button after recreation; this is intentionally not automated by the image.

The selected xrdp 0.10 GFX path was responsive during real QMT login and resize
acceptance. A controlled xrdp 0.9 versus 0.10 CPU/bandwidth benchmark remains a
separate performance evidence task; no VNC fallback is implied by that work.
