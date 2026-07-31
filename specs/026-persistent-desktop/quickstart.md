# Quickstart: Secure Persistent Desktop

This document describes the implemented operator flow. The native session POC,
real QMT acceptance, and hardened NAS rollout passed on 2026-08-01.

## Immediate Containment for Existing Deployments

Before waiting for 026 implementation:

1. Replace the development RDP password `qmt` with a unique strong password.
2. Restrict host port 13389 to loopback, a VPN interface, or an explicit LAN
   source allowlist. Do not forward it from the internet.
3. Put MCP behind TLS or keep it on a controlled private network.
4. Re-run `appliance/scripts/harden-check.sh appliance/.env` and resolve every
   failure.

The current xrdp 0.9.24 package remains vulnerable even after a password
change, so network restriction is required until the image upgrade ships.

## Intended Configuration

Create a gitignored secret file containing the desktop password and configure:

```env
QMT_DESKTOP_MODE=persistent
QMT_RDP_PASSWORD_FILE=/run/secrets/qmt_rdp_password
RDP_BIND_ADDRESS=127.0.0.1
RDP_PORT=13389
QMT_RDP_CLIPBOARD=none
QMT_RDP_DRIVE_REDIRECTION=0
```

The shared Compose service keeps a per-instance RDP certificate volume and has
no password default. `QMT_RDP_PASSWORD_FILE` is a container path, so mount the
owner-only host file with a small local override:

```yaml
services:
  qmt:
    volumes:
      - ${QMT_RDP_PASSWORD_HOST_FILE:?set the host secret path}:/run/secrets/qmt_rdp_password:ro
```

Set `QMT_RDP_PASSWORD_HOST_FILE` to the host file and keep
`QMT_RDP_PASSWORD_FILE=/run/secrets/qmt_rdp_password`. Environment input remains
available for compatibility but is visible in container metadata.

## First QMT Login

1. Start the appliance. The desktop session is created even though no RDP
   client is connected.
2. Open an SSH tunnel from the operator workstation:

```bash
ssh -L 13389:127.0.0.1:13389 <nas-user>@<nas-host>
```

3. Connect Windows App to `127.0.0.1:13389` as `wineuser`.
4. Confirm the connection opens the already-running XFCE/QMT desktop.
5. Complete QMT broker login, captcha, agreements, or upgrades manually.
6. Disconnect RDP without logging out.
7. Verify MCP liveness and xtdata readiness separately.

## Restart Acceptance

After QMT login state is saved in the broker pack:

```bash
docker compose up -d --force-recreate
```

Without opening RDP, verify:

- one Xorg/XFCE session
- one QMT terminal tree
- one MCP supervisor
- MCP `/livez` succeeds
- `/healthz` accurately reports xtdata readiness

Reconnect Windows App and verify it shows the same display and process
generation rather than launching a second QMT.

## Manual Recovery

Set `QMT_DESKTOP_MODE=manual` and recreate the container. xrdp remains patched
and hardened, but the desktop starts only after an operator login. This mode is
for diagnosis and rollback, not the unattended steady state.
