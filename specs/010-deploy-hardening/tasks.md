# Tasks: Deploy & Security Hardening

- [x] T001 `scripts/harden-check.sh` — pre-flight: weak/default token, default RDP
  password, public bind, TLS reminder; non-zero on hard fail; no secret echo.
- [x] T002 `deploy/Caddyfile.example` — TLS termination, reverse-proxy to MCP,
  forward `Authorization`, health via `/livez`.
- [x] T003 `docker-compose.tls.yml` — add Caddy, keep MCP port internal (expose,
  not publish), mount certs/Caddyfile.
- [x] T004 `docs/DEPLOY.md` — threat model, topology, token strength, RDP exposure,
  TLS options, token rotation, deploy checklist.
- [x] T005 Verify: `bash -n harden-check.sh`; run with weak env (exit!=0) and
  strong env (exit 0); compose/YAML parse for the override.
