# Quickstart: Optional VNC Access

VNC is an optional client protocol for the existing persistent QMT desktop. It
does not start another QMT session.

```bash
cd appliance
cp .env.example .env
# Set BROKER_PACK, QMT_MCP_TOKEN, a strong RDP password, and:
# QMT_DESKTOP_MODE=persistent
# Leave both VNC password inputs empty for the first smoke test to reuse the
# resolved RDP password, or mount a unique secret as described below.

docker compose -f docker-compose.yml -f docker-compose.vnc.yml up -d
```

The VNC override publishes `127.0.0.1:15900` by default. Connect through an SSH
tunnel from the client machine:

```bash
ssh -N -L 15900:127.0.0.1:15900 <nas>
```

Then point a VNC client at `127.0.0.1:15900` and save the VNC credential in that
client if desired. RDP remains at loopback port 13389 and shows the same desktop.

For a long-lived deployment, mount an owner-only file through a
deployment-specific Compose secret or read-only bind, then set
`QMT_VNC_PASSWORD_FILE` to its in-container path. The example
`/run/secrets/qmt_vnc_password` path is not mounted by the base Compose file.

Raw VNC is not transport-encrypted. Do not expose port 15900 directly to the
internet. Classic VNC authentication uses only the first eight password
characters, so use a unique random value and do not reuse an important account
password.

Check status without revealing credentials:

```bash
docker exec qmt-<instance> cat /run/qmt/desktop/status.json
docker exec qmt-<instance> pgrep -af 'Xorg|x11vnc|XtItClient|qmt_mcp.py'
```

Expected: one Xorg, one x11vnc, one QMT root, one MCP process, and status fields
`vnc_enabled=true` plus `vnc_ready=true`.
