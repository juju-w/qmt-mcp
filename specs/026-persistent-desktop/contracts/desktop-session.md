# Contract: Persistent Desktop and RDP Policy

## Configuration

Proposed names are fixed by this contract; implementation may add deprecated
aliases only for migration.

| Variable | Default | Contract |
|---|---|---|
| `QMT_DESKTOP_MODE` | `manual` | `manual` or `persistent` |
| `QMT_RDP_PASSWORD_FILE` | empty | Preferred container path to an owner-only secret file |
| `QMT_RDP_PASSWORD` | empty | Compatibility input; never defaulted and never written onward |
| `QMT_RDP_GEOMETRY` | `1440x900x32` | Valid bounded bootstrap geometry |
| `QMT_RDP_CLIPBOARD` | `none` | `none`, `text`, or `all`; file/drive remains separately gated |
| `QMT_RDP_DRIVE_REDIRECTION` | `0` | `1` requires explicit unsafe-capability acknowledgement |
| `QMT_RDP_CERT_MODE` | `generated` | `generated` or `mounted` |
| `QMT_RDP_CERT_FILE` | instance runtime path | Mounted certificate when mode is `mounted` |
| `QMT_RDP_KEY_FILE` | instance runtime path | Mounted private key when mode is `mounted` |
| `QMT_RDP_BOOT_RETRIES` | `3` | Bounded integer, 0 through 10 |
| `QMT_RDP_BOOT_BACKOFF_S` | `5` | Bounded integer, 1 through 60 |
| `QMT_RDP_ALLOW_LAN` | `0` | Required acknowledgement for non-loopback publishing |
| `QMT_RDP_ALLOW_UNSAFE_CHANNELS` | `0` | Required when drive/file channel policy is enabled |

Compose host interpolation:

| Variable | Default | Contract |
|---|---|---|
| `RDP_BIND_ADDRESS` | `127.0.0.1` | Host address used in published-port syntax |
| `RDP_PORT` | `13389` | Host TCP port |
| `RDP_CERT_VOLUME` | instance-scoped | Persistent certificate/key storage |

`RDP_BIND_ADDRESS=0.0.0.0` or `::` is invalid unless
`QMT_RDP_ALLOW_LAN=1`. Even with that acknowledgement, internet exposure is
unsupported and the audit must warn unless a VPN or host allowlist is declared.

## Secret Resolution

1. If `QMT_RDP_PASSWORD_FILE` is set, it must be a regular, non-empty,
   non-world-readable file. Read one logical line and remove only its line
   terminator.
2. Otherwise, a non-empty `QMT_RDP_PASSWORD` is accepted for compatibility.
3. Reject known defaults and policy-invalid values before starting xrdp.
4. Feed bootstrap authentication to `xrdp-sesrun` over file descriptor 0 with
   `-F 0`. Never use `-p`.
5. Never place the resolved value in `/opt/qmt-mcp/mcp.env`, command arguments,
   logs, status JSON, image history, or generated ini files.

## Startup Modes

### `manual`

- Start patched and hardened xrdp/xrdp-sesman.
- Do not pre-create an Xorg session.
- An operator login creates or reconnects the desktop.
- Existing behavior remains available for diagnosis and rollback.

### `persistent`

- Validate secrets, certificate storage, and security policy.
- Start xrdp-sesman and xrdp.
- Wait for the local sesman control endpoint with a bounded deadline.
- Acquire the desktop singleton lease.
- Start one Xorg session for the configured user using secure FD input.
- Verify the display, XFCE session, QMT singleton, and MCP supervisor.
- Keep disconnected sessions alive and make a later RDP login reattach.
- On failure, clean stale state and retry within the configured budget.

If the native POC shows that `xrdp-sesrun` cannot create a reliably
reattachable session, this contract must be revised before implementation.

## Session Invariants

- At most one active Xorg/XFCE desktop for `wineuser`.
- At most one QMT terminal root process for the configured client.
- At most one MCP supervisor and one serving MCP child.
- An RDP attach or resolution change does not alter these counts.
- A QMT helper process is part of the existing QMT tree, not a duplicate.
- A duplicate attempt is rejected without killing the established session.

## TLS Contract

- `security_layer=tls`
- TLS 1.2 and TLS 1.3 only
- no classic RDP fallback
- no image-baked or cross-instance private key
- generated certificates persist across ordinary container recreation
- mounted key permissions are checked before listener startup
- audit output includes fingerprint and expiry, never the private key

## Desktop Authorization Contract

- `AllowRootLogin=false`
- a dedicated terminal-server group exists
- `AlwaysGroupCheck=true`
- only the configured desktop user belongs to that group
- desktop user has no sudo/admin membership
- password attempts are bounded by the patched xrdp implementation and network
  exposure remains restricted outside the application

## Channel Contract

Default:

- client drive and file redirection disabled
- clipboard disabled
- remote audio optional and documented
- unsupported virtual channels disabled

An operator may enable text clipboard without enabling files or drives. Broad
channel enablement requires explicit acknowledgement and an audit warning.

## Runtime Status

`/run/qmt/desktop/status.json` is atomically replaced and owner-readable. It may
contain:

```json
{
  "generationId": "opaque-non-secret-id",
  "mode": "persistent",
  "state": "desktop_ready",
  "reason": "session_verified",
  "attempt": 1,
  "display": 10,
  "sessionId": 1,
  "updatedAt": "2026-07-31T15:00:00Z"
}
```

PID fields may be included for local diagnostics. Passwords, access tokens,
broker credentials, account identifiers, and raw QMT UI text are forbidden.

## Audit Command

The deployment audit exits non-zero for:

- missing/default password or insecure secret-file permissions
- wildcard publishing without explicit acknowledgement
- wildcard IPv6 when only loopback was requested
- xrdp/xorgxrdp version below or different from the pin
- classic RDP negotiation or TLS below 1.2
- inherited/shared/private-key-in-image certificate state
- root login, no login-group enforcement, or desktop sudo membership
- forbidden drive/file channels
- more than one desktop, QMT root, or MCP supervisor

Warnings cover intentionally enabled text clipboard, LAN/VPN publishing,
certificate expiry horizon, and manual mode awaiting login.
