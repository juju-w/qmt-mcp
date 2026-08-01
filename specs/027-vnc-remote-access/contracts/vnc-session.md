# Contract: VNC Access to the Persistent Desktop

## Configuration

| Variable | Default | Contract |
|---|---|---|
| `QMT_VNC_ENABLED` | `0` | Boolean opt-in; requires persistent desktop mode |
| `QMT_VNC_PASSWORD_FILE` | empty | Preferred owner-only regular secret file |
| `QMT_VNC_PASSWORD` | empty | Compatibility environment input |
| `QMT_VNC_ALLOW_LAN` | `0` | Required for non-loopback host publication |
| `QMT_VNC_CLIPBOARD` | `none` | `none` or `text`; default closes clipboard |
| `QMT_VNC_RESTART_BACKOFF_S` | `2` | Bounded adapter restart delay, 1 through 60 |
| `VNC_BIND_ADDRESS` | `127.0.0.1` | Host address used by VNC Compose override |
| `VNC_PORT` | `15900` | Host TCP port mapped to container 5900 |

## Enablement

- `QMT_VNC_ENABLED=0`: no x11vnc process or auth file is permitted.
- `QMT_VNC_ENABLED=1`: `QMT_DESKTOP_MODE` must equal `persistent`.
- Publishing VNC requires the explicit VNC Compose override.
- A non-loopback `VNC_BIND_ADDRESS` requires `QMT_VNC_ALLOW_LAN=1`.
- Internet publication is unsupported even with acknowledgement.

## Secret Resolution

1. Use `QMT_VNC_PASSWORD_FILE` when set; require readable regular file, no
   symlink, and no group/other permissions.
2. Otherwise use non-empty `QMT_VNC_PASSWORD`.
3. Otherwise deliberately fall back to the already-resolved RDP password.
4. Reject empty, known-default, or fewer-than-eight-character values.
5. Pipe the value to `tigervncpasswd -f`; never use a password argument.
6. Install `/run/qmt/vnc/passwd` mode 0600 owned by `wineuser`.
7. Unset plaintext variables before xrdp, supervisor, or x11vnc starts.

Only the first eight characters are effective under classic VNC
authentication. The file is obfuscated, not encrypted, and is recreated at
container startup.

## Process Contract

x11vnc is launched only after the persistent supervisor has verified:

- the Xorg PID is alive;
- the selected display exists;
- the `wineuser` Xauthority is readable;
- no other x11vnc adapter for the display is alive.

The required baseline is equivalent to:

```text
x11vnc -display :<display> -auth /home/wineuser/.Xauthority
  -rfbport 5900 -rfbauth /run/qmt/vnc/passwd
  -forever -shared -noxdamage -repeat
  -notightfilexfer -safer -nocmds
```

Clipboard-disabled mode adds the supported x11vnc clipboard suppression flags.
The server listens on the container interface; Docker host publication owns the
loopback/LAN boundary.

## Session Invariants

- x11vnc creates no X server, desktop manager, QMT, Wine, or MCP process.
- RDP and VNC show display `:<display>` from the same status record.
- Connecting or disconnecting either protocol does not change Xorg/QMT/MCP
  identities.
- Killing x11vnc changes only the VNC PID and readiness.
- Container shutdown stops x11vnc before terminating the persistent display.

## Runtime Status

`/run/qmt/desktop/status.json` schema version 2 includes:

```json
{
  "schema_version": 2,
  "mode": "persistent",
  "state": "ready",
  "display": ":10",
  "xorg_pid": 123,
  "mcp_ready": true,
  "vnc_enabled": true,
  "vnc_ready": true,
  "vnc_pid": 456,
  "updated_at": "2026-08-01T00:00:00Z"
}
```

No password, auth-file contents, token, broker credential, account identifier,
or raw desktop content may appear.
