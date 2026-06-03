# Security Policy

This project is a **trading appliance**: it runs a broker's QMT/MiniQMT terminal
under Wine and exposes market-data and (opt-in) account-query capabilities to AI
agents over MCP. Because it can sit close to real brokerage accounts, please
treat security reports seriously and handle them privately.

## Reporting a vulnerability

**Do not open a public issue for security problems.**

- Preferred: use GitHub's **"Report a vulnerability"** (Security → Advisories) on
  this repository for a private report.
- Alternatively, email the maintainer: **kuijuwang@gmail.com** with subject
  `SECURITY: qmt_in_mac`.

Please include: affected component/path, version/commit, reproduction steps, and
impact. A minimal proof of concept helps.

### Response window

Best-effort acknowledgement within **5 business days**, and a remediation plan or
fix discussion thereafter. This is a community project, not a vendor SLA.

## Scope

**In scope** (this repository):

- The MCP core (`qmt-wine-rdp/mcp/qmt_mcp_core`) — auth, token handling, audit,
  error envelopes, tool allow-listing.
- The xtdata/search tool layer (`qmt-wine-rdp/mcp/qmt_mcp_xtdata`).
- Launch/entrypoint scripts, Dockerfile, and compose (network exposure, secrets
  handling, RDP defaults, tmpfs guard).

**Out of scope**:

- The proprietary QMT terminal and `xtquant` (report to the broker / 迅投).
- The upstream base image (`scottyhardy/docker-wine`) — report upstream.
- Findings that require an already-compromised host or physical access.

## Rules of engagement

- **Never test against a production broker login or a live trading account.** Use
  a disabled / unauthorized account, and never place orders. This project ships
  read-only by default and has no write/trade tools enabled.
- Do not attempt to access data or accounts that are not yours.
- Do not run denial-of-service or load tests against shared infrastructure.

## Secrets model (by design)

- The MCP endpoint requires a **bearer token**; it is never baked into images or
  committed (`.env` is git-ignored).
- **Trading credentials live only in the operator's interactive QMT login
  session** — never in `broker.yaml`, config, image layers, or git history.
- Audit logs redact secret-looking fields (token/password/secret/cookie/...).

If you find a secret committed to history, report it privately and we will rotate
and purge it.
