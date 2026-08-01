# Research: VNC Remote Access

**Date**: 2026-08-01

## Requirement Correction

PR #19 was initially evaluated mainly as an unattended-start proposal. The
author later clarified that the durable requirement is VNC workflow and client
flexibility: clients can retain the VNC credential for one-action reconnects,
and lightweight clients are broadly available, especially on Android.

Persistent RDP in 026 solved unattended startup but did not satisfy that client
protocol requirement. Spec 027 therefore supersedes 026's decision that VNC is
redundant. It retains the secure persistent desktop and adds VNC to that same
session.

## PR #19 Findings

The proposal usefully established that:

- x11vnc adds modest image/runtime overhead compared with noVNC;
- raw VNC is enough for one-off login and mobile troubleshooting;
- a window manager is necessary because bare QMT dialogs can be unreachable;
- `-forever -shared -noxdamage -repeat` is a practical baseline for QMT;
- authentication must be mandatory and the listener must be supervised.

Its implementation predates 026 and now conflicts with required invariants:

- `vnc` creates a separate Xvfb/XFCE/QMT/MCP session;
- `both` knowingly lets RDP create another X session and potentially another
  QMT against one Wine prefix;
- Compose publishes VNC on all host interfaces even in default RDP mode;
- `x11vnc -storepasswd "$QMT_VNC_PASSWORD"` puts plaintext in argv briefly;
- the plaintext value is written into `mcp.env`;
- loss of x11vnc terminates the full session/container instead of isolating the
  optional access adapter.

The implementation will credit the author while replacing these mechanics.

## x11vnc and Authentication Evidence

The x11vnc manual documents `-display`, `-auth`, `-rfbauth`, `-listen`,
`-forever`, `-shared`, `-noxdamage`, `-repeat`, `-notightfilexfer`, and
`-nocmds`. In x11vnc 0.9.16, TightVNC file transfer defaults off and
`-notightfilexfer` makes that policy explicit; UltraVNC transfer is enabled
only by the absent `-ultrafilexfer` option. `-safer` and `-nocmds` close
remote-control and external-command channels. Password protection is not
enabled automatically.

TigerVNC `vncpasswd -f` filter mode reads plaintext from standard input and
writes the obfuscated VNC password file to standard output. That avoids a
plaintext command argument. The auth file is not cryptographically protected
at rest and must remain owner-only and ephemeral.

Classic VNC authentication effectively uses the first eight password
characters. It authenticates the RFB session but does not encrypt the desktop
transport. Host-loopback publication plus SSH/VPN is therefore the default;
public raw VNC is unsupported.

Sources:

- https://github.com/libvnc/x11vnc
- https://manpages.ubuntu.com/manpages/noble/man1/x11vnc.1.html
- https://manpages.debian.org/testing/tigervnc-tools/vncpasswd.1.en.html
- https://github.com/juju-w/qmt-mcp/pull/19

## Selected Design

- `QMT_VNC_ENABLED=0` leaves image behavior and host publication unchanged.
- The VNC Compose override enables the adapter and publishes loopback port
  15900.
- VNC is valid only with `QMT_DESKTOP_MODE=persistent`.
- x11vnc reads the persistent display and `/home/wineuser/.Xauthority`.
- RDP and VNC may connect concurrently to that display.
- VNC failure is observable and recoverable without recreating QMT or MCP.
- Clipboard and file-transfer capabilities are closed by default.

## Rejected Alternatives

### Separate Xvfb VNC mode

Rejected because it duplicates desktop ownership and makes RDP/VNC switching
unsafe against one Wine prefix. It also regresses the native-tested 026
lifecycle.

### Treat persistent RDP as a substitute

Rejected because it does not provide VNC credential persistence or the Android
and lightweight client ecosystem requested by the contributor and owner.

### noVNC

Rejected for this feature because browser delivery adds websockify, browser
assets, another exposed route, and more packages without improving the stated
native-client workflow.

### Unauthenticated or public VNC

Rejected because the display can control a live brokerage terminal and raw VNC
does not provide adequate internet transport security.
