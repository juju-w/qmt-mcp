# Deployment & Hardening

The dev `docker-compose.yml` publishes the MCP and RDP ports directly and ships a
weak default RDP password — convenient on a loopback box, **unsafe if exposed**.
This guide covers deploying the appliance where others (or agents on other hosts)
can reach it.

> Run `scripts/harden-check.sh` before any non-loopback deploy. It fails on weak
> tokens / default passwords / undeclared exposure.

## Threat model

What the appliance guards:

- The **MCP endpoint** can read market data and (if enabled, with broker
  permission) query account state. It is bearer-token authenticated.
- The **RDP desktop** is where a human logs into the live QMT terminal — i.e. it
  is adjacent to a real brokerage login.

Primary risks: an unauthenticated/weakly-authenticated MCP on an open network; a
bearer token sniffed over plain HTTP; an exposed RDP port brute-forced to reach a
trading session.

## Recommended topology

```text
agent ──HTTPS──> Caddy (TLS, :443) ──http──> qmt:8765 (MCP, internal only)
operator ──VPN/tunnel──> 127.0.0.1:3389 (RDP, loopback only)
```

- MCP is **not** published to the host; the TLS proxy reaches it on the compose
  network. (`docker-compose.tls.yml` + `deploy/Caddyfile.example`.)
- RDP is bound to loopback; reach it through a VPN/SSH tunnel, never the public
  internet.

## Bearer token

- Generate a strong random token: `openssl rand -hex 32`.
- Put it in `appliance/.env` as `QMT_MCP_TOKEN=...` (git-ignored). Never bake
  it into an image or commit it.
- **Rotation**: change `QMT_MCP_TOKEN` and recreate the MCP (e.g.
  `docker compose up -d`). Rotation invalidates existing agent sessions — update
  clients/`qmtctl` config accordingly. Rotate on suspected exposure or staff
  changes.

## TLS

- Public domain: use the Caddy example — it auto-provisions Let's Encrypt certs.
- Internal only: use Caddy's internal CA (`tls internal`) or terminate TLS at an
  existing ingress.
- Plain HTTP is acceptable **only** on `127.0.0.1` for local dev. A bearer token
  over plain HTTP on a LAN is sniffable.

## RDP

- Set a strong `QMT_RDP_PASSWORD` (the compose default `qmt` is for dev only).
- Bind to loopback (`127.0.0.1:3389`) and tunnel in; do not publish RDP publicly.

## Storage

- The broker pack / userdata MUST live on **real disk**, never tmpfs (RAM
  exhaustion — see 001). 005's entrypoint guard enforces this; until then, verify
  manually.

## Audit

- The MCP writes an append-only JSONL audit log (`/broker/logs/mcp-audit.jsonl`).
  Ship/retain it for incident review; it redacts secret-looking fields.

## Pre-deploy checklist

- [ ] `scripts/harden-check.sh` passes (no `[FAIL]`).
- [ ] `QMT_MCP_TOKEN` is random and >= 32 chars; stored only in `.env`.
- [ ] `QMT_RDP_PASSWORD` is strong and non-default.
- [ ] MCP reachable only via TLS proxy (not host-published on a LAN).
- [ ] RDP bound to loopback / behind VPN.
- [ ] Broker pack on real disk (not tmpfs).
- [ ] Audit log destination is persistent and monitored.
- [ ] Read-only mode confirmed (no write/trade tools enabled).
