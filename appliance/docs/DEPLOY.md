# Deployment & Hardening

The dev `docker-compose.yml` publishes the MCP and RDP ports directly and ships a
weak default RDP password — convenient on a loopback box, **unsafe if exposed**.
This guide covers deploying the appliance where others (or agents on other hosts)
can reach it.

> Run `scripts/harden-check.sh` before any non-loopback deploy. It fails on
> incomplete authentication, weak static tokens, default passwords, or
> undeclared exposure.

## Threat model

What the appliance guards:

- The **MCP endpoint** can read market data and (if enabled, with broker
  permission) query account state. It accepts a static bearer, a verified OAuth
  JWT, or both according to the configured auth mode.
- The **RDP desktop** is where a human logs into the live QMT terminal — i.e. it
  is adjacent to a real brokerage login.

Primary risks: an unauthenticated/weakly-authenticated MCP on an open network; a
bearer credential sniffed over plain HTTP; an over-scoped token; or an exposed
RDP port brute-forced to reach a trading session.

## Recommended topology

```text
agent ──HTTPS──> Caddy (TLS, :443) ──http──> qmt:8765 (MCP, internal only)
operator ──VPN/tunnel──> 127.0.0.1:3389 (RDP, loopback only)
```

- MCP is **not** published to the host; the TLS proxy reaches it on the compose
  network. (`docker-compose.tls.yml` + `deploy/Caddyfile.example`.)
- RDP is bound to loopback; reach it through a VPN/SSH tunnel, never the public
  internet.

## Authentication modes

| Mode | Required configuration | Use |
|---|---|---|
| `static` | strong `QMT_MCP_TOKEN` | default, personal NAS or controlled network |
| `oauth` | external issuer/JWKS/resource | public or multi-user least privilege |
| `hybrid` | both static and OAuth configuration | staged migration |

For static or hybrid mode, generate `QMT_MCP_TOKEN` with
`openssl rand -hex 32`. Keep it only in gitignored `appliance/.env`. Rotate it
by updating the env file and recreating the service.

## OAuth JWT resource server

QMT-MCP publishes MCP OAuth 2.1 protected-resource metadata and validates
asymmetric JWT access tokens itself. It remains the resource server: login,
consent, authorization codes, token issuance, and client registration belong to
an external authorization server. Opaque-token introspection is not supported.

Set these variables when publishing through HTTPS:

```env
QMT_MCP_AUTH_MODE=oauth
QMT_MCP_PUBLIC_BASE_URL=https://qmt.example.com
QMT_MCP_OAUTH_ISSUER=https://auth.example.com
QMT_MCP_OAUTH_AUTHORIZATION_SERVERS=https://auth.example.com
QMT_MCP_OAUTH_JWKS_URL=https://auth.example.com/.well-known/jwks.json
QMT_MCP_OAUTH_RESOURCE=https://qmt.example.com/mcp
QMT_MCP_OAUTH_RESOURCE_NAME=QMT MCP
QMT_MCP_OAUTH_SCOPES=qmt:read qmt:market qmt:account qmt:manage qmt:admin
QMT_MCP_OAUTH_ALGORITHMS=RS256 ES256
```

When enabled, unauthenticated MCP requests include a `WWW-Authenticate` challenge
with `resource_metadata`, and the metadata document is served at
both RFC 9728 path forms. Tokens must carry the exact issuer, MCP resource
audience, expiry, client identity, allowed asymmetric algorithm, signing-key id,
and scopes. JWKS fetches have bounded timeout/size/cache controls and refresh
once for an unknown `kid`.

Scopes are `qmt:read` (required core), `qmt:market`, `qmt:account`,
`qmt:manage` (non-trading mutation within an already granted family), and
`qmt:admin`. Effective access is the intersection of feature gates, startup
Profile/allow/deny policy, and token scopes. No scope enables trading.

Use `qmtctl auth login` for browser Authorization Code + PKCE, persisted refresh,
status, and logout. See `docs/MCP-CLIENTS.md`.

## TLS

- Public domain: use the Caddy example — it auto-provisions Let's Encrypt certs.
- Internal only: use Caddy's internal CA (`tls internal`) or terminate TLS at an
  existing ingress.
- Plain HTTP is acceptable **only** on loopback for local dev. Any bearer
  credential over plain HTTP on a LAN is sniffable.

## Pagination and compression

`tools/list` is server-paginated after Profile and OAuth filtering. The default
page size is 50 and qmtctl automatically follows every opaque cursor:

```env
QMT_MCP_LIST_PAGE_SIZE=50
```

Eligible MCP JSON responses use negotiated gzip above 1024 bytes. SSE is
excluded to preserve incremental delivery:

```env
QMT_MCP_GZIP_MIN_SIZE=1024
```

Leave this enabled when the upstream proxy passes `Accept-Encoding` through.
Set it to `0` when the ingress is the sole compression layer. The middleware
does not double-compress an already encoded response and emits
`Vary: Accept-Encoding`.

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
- [ ] Auth mode is intentional; static/hybrid token is random and >= 32 chars.
- [ ] OAuth/hybrid pins one HTTPS issuer, JWKS URL, resource, asymmetric
      algorithm allowlist, and only the scopes actually needed.
- [ ] `QMT_RDP_PASSWORD` is strong and non-default.
- [ ] MCP reachable only via TLS proxy (not host-published on a LAN).
- [ ] Compression ownership is intentional; app gzip is disabled if the
      ingress must be the only compressor.
- [ ] RDP bound to loopback / behind VPN.
- [ ] Broker pack on real disk (not tmpfs).
- [ ] Audit log destination is persistent and monitored.
- [ ] No trade tools exist; optional managed-sector/formula mutations and their
      `qmt:manage` grants are intentional.
