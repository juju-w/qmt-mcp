# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Versioning policy

Pre-1.0: the broker-pack contract and exposed MCP tool surface are still evolving;
minor versions may include breaking changes (noted explicitly). After 1.0, a
**breaking change to the broker-pack contract or the exposed tool surface** is a
major bump and ships with a migration note (per the project constitution's quality
gates).

## [Unreleased]

No unreleased changes yet.

## [0.2.0] - 2026-06-04

### Added
- **001 — Broker-agnostic base image + broker pack**: Wine (new WoW64) + Windows
  Python 3.12 + CJK fonts + xrdp; broker-neutral base with the QMT terminal /
  `xtquant` / `broker.yaml` mounted at `/broker` at runtime.
- **002 — MCP server core**: bearer auth, explicit tool registry, capability-gated
  tool families, `/healthz`, uniform error envelopes, worker-backed calls, JSONL
  audit.
- **003 — Market-data (xtdata) tools**: curated read-only xtdata tool family
  (11/11 verified live).
- **006 — Instrument-search tools**: persistent search cache/index/seed.
- **008 — CI & test foundation**: host-runnable pytest unit tier (no Wine/xtquant),
  optional fastmcp integration tier, ruff lint+format, GitHub Actions (lint, unit,
  gitleaks, conditional Go build). Made `qmt_mcp_core` importable without `fastmcp`
  (lazy `__init__`); registered the `config` startup error type.
- **009 — Open-source readiness**: root `LICENSE` (MIT), `SECURITY.md`,
  `CONTRIBUTING.md`; README license link.
- **010 — Deploy & hardening**: `docs/DEPLOY.md`, Caddy TLS reverse-proxy example,
  `docker-compose.tls.yml` (MCP internal-only), `scripts/harden-check.sh` pre-flight.
- **005 — Supervision, readiness & autostart** (core): live readiness probe +
  `/healthz` `readiness` object, unauthenticated `/livez`, background trader
  connector, session supervisor + `HEALTHCHECK`, tmpfs storage guard (warn-by-
  default). Container behaviors pending amd64 validation (see specs/005).
- **004 — Account-query tools** (read-only, opt-in): `xttrade_query` family
  (`asset/positions/orders/trades/...`) behind an enable flag + account allowlist,
  readiness-gated, audited. Success paths need a broker-permissioned account
  (community PR); boundary/gating host-tested.
- **012 — Database persistence (PostgreSQL, optional)**: native-async (`asyncpg`)
  layer behind a sync facade; opt-in via `QMT_DB_URL` (external) or a compose
  `db` profile; market-data warehouse with bars read-through/write-through;
  graceful degradation; `health.database`. Tested for real against PostgreSQL 16.
  Off by default (file/JSONL unchanged).
- **007 — qmtctl CLI**: compiled Go CLI for streamable-http MCP with health,
  tools, xtdata search/resolve/snapshot/bars/cache/smoke commands, read-only
  xttrade account-query wrappers, NAS appliance smoke verification, and release
  binaries for Linux/macOS/Windows on amd64+arm64.

### Planned
- **011 — Release & versioning**: this scaffolding.

### Known gaps
- In-image pip deps are declared in `appliance/mcp/requirements.in`; the locked
  `requirements.txt` must be generated from an amd64 Wine build (constitution III).

[Unreleased]: https://github.com/juju-w/qmt-mcp/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/juju-w/qmt-mcp/compare/v0.1.0...v0.2.0
