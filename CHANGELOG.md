# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Versioning policy

This project follows Conventional Commits and Semantic Versioning: `feat` bumps
minor, other accepted non-breaking types bump patch, and `!` or a
`BREAKING CHANGE:` footer bumps major. A breaking change to the broker-pack
contract or exposed MCP tool surface also requires a migration note under the
project constitution's quality gates.

## [Unreleased]

No unreleased changes yet.

## [0.14.4] - 2026-08-03

See the generated GitHub release notes for the complete change list.

## [0.14.3] - 2026-08-03

See the generated GitHub release notes for the complete change list.

## [0.14.2] - 2026-08-03

See the generated GitHub release notes for the complete change list.

## [0.14.1] - 2026-08-03

See the generated GitHub release notes for the complete change list.

## [0.14.0] - 2026-08-03

See the generated GitHub release notes for the complete change list.

## [0.13.1] - 2026-08-01

See the generated GitHub release notes for the complete change list.

## [0.13.0] - 2026-08-01

See the generated GitHub release notes for the complete change list.

## [0.12.1] - 2026-07-31

See the generated GitHub release notes for the complete change list.

## [0.12.0] - 2026-07-31

See the generated GitHub release notes for the complete change list.

## [0.11.1] - 2026-07-30

See the generated GitHub release notes for the complete change list.

## [0.11.0] - 2026-07-30

See the generated GitHub release notes for the complete change list.

## [0.10.0] - 2026-07-30

See the generated GitHub release notes for the complete change list.

## [0.9.0] - 2026-07-30

See the generated GitHub release notes for the complete change list.

## [0.8.0] - 2026-07-30

See the generated GitHub release notes for the complete change list.

## [0.7.0] - 2026-07-30

See the generated GitHub release notes for the complete change list.

## [0.6.0] - 2026-07-30

See the generated GitHub release notes for the complete change list.

## [0.5.0] - 2026-07-30

See the generated GitHub release notes for the complete change list.

## [0.4.3] - 2026-07-30

### Added
- Added a standard `AGENTS.md` discovery entry that points coding agents to the
  repository's canonical development guide.

### Changed
- Updated the QMT operation and deployment skills for the complete qmtctl
  command surface, OAuth protected-resource discovery, current tool families,
  and optional write gates.
- Centralized Conventional Commit, CI, automatic release, Docker layer, and
  build-cache rules in `AGENT.md`.
- The deployment verifier now accepts `QMT_MCP_ACCESS_TOKEN`, with precedence
  over the static `QMT_MCP_TOKEN`, matching qmtctl.

## [0.4.2] - 2026-07-30

### Fixed
- Historical release retries can read but no longer overwrite the shared
  BuildKit cache used by the latest release line.

## [0.4.1] - 2026-07-30

### Fixed
- Manual retries can publish releases for older tags whose commits contain
  historical workflow files without requiring a broad personal access token.

## [0.4.0] - 2026-07-30

### Added
- qmtctl can inspect OAuth protected-resource metadata with `qmtctl auth
  discover` and accepts bearer access tokens through `--access-token` or
  `QMT_MCP_ACCESS_TOKEN`.
- qmtctl exposes `version`; release binaries report the SemVer embedded during
  cross-compilation and send it in the MCP initialize handshake.
- Releases can optionally mirror the already-built GHCR image digest to a
  mainland China registry without rebuilding it.

### Changed
- The appliance Dockerfile keeps Wine/Python dependency provisioning ahead of
  frequently changing MCP source, so source-only releases reuse the heavy layer.
- Image builds use a persistent GHCR BuildKit cache with the previous GitHub
  Actions cache as a migration fallback.
- Manual release runs can rebuild and republish an existing version tag.

### Fixed
- GitHub Release creation now requests job-level write permission and passes the
  release token explicitly instead of relying on an action default.
- qmtctl strategy JSON imports sort deduplicated instrument codes, removing
  platform-dependent output caused by Go map iteration.

## [0.3.1] - 2026-07-30

### Changed
- GitHub Actions are pinned to current Node 24-compatible releases, removing the
  Node 20 deprecation path from CI, artifact publishing, image builds, secret
  scanning, and GitHub Release creation.

## [0.3.0] - 2026-07-30

### Changed
- CI now enforces Conventional Commit subjects and PR titles without duplicate
  branch/PR runs. A successful `main` CI run automatically updates `VERSION` and
  this changelog, tags the release, builds the GHCR appliance image, packages
  qmtctl for six OS/architecture targets, publishes checksums, and creates the
  GitHub Release.

### Added
- **013 — Quote subscription cache**: `qmt_xtdata_quote_subscribe` /
  `unsubscribe` / `subscriptions` / `subscription_status` tools + `qmtctl
  subscription` subcommands. Official `subscribe_quote` preferred, bounded
  polling fallback; in-memory hot cache (<1 ms lookup).
- **014 — Portfolio risk analysis** (read-only): `qmt_portfolio_summary` /
  `positions` / `exposure` / `risk_checks` tools + `qmtctl portfolio`
  subcommands. Depends on xttrade account allowlist.
- **015 — Option & volatility data** (read-only): `qmt_xtdata_option_chain` /
  `option_quotes` / `option_iv` / `volatility_index_inputs` tools + `qmtctl
  option` subcommands. No index value publishing.
- **016 — xtdata reference data** (read-only, capability-gated):
  `qmt_xtdata_financial_data` / `ipo_info` / `dividend_factors` / `cb_info` /
  `etf_info` tools + `qmtctl ref` subcommands.
- **017 — Custom sector management** (off by default): `qmt_xtdata_sector_create`
  / `sector_add_codes` / `sector_remove_codes` / `managed_sector_list` tools +
  `qmtctl sector` subcommands. Managed-prefix sandbox (`MCP/`, `AI/`, etc.).
- **018 — Formula / factor runtime** (off by default): `qmt_xtdata_formula_call`
  / `formula_call_batch` / `formula_generate_factor` / `formula_subscribe`
  tools + `qmtctl formula` subcommands. Server-side allowlist + output sandbox.

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

### Known gaps
- In-image pip deps are declared in `appliance/mcp/requirements.in`; the locked
  `requirements.txt` must be generated from an amd64 Wine build (constitution III).

[Unreleased]: https://github.com/juju-w/qmt-mcp/compare/v0.14.4...HEAD
[0.2.0]: https://github.com/juju-w/qmt-mcp/compare/v0.1.0...v0.2.0
[0.3.0]: https://github.com/juju-w/qmt-mcp/compare/v0.2.0...v0.3.0
[0.3.1]: https://github.com/juju-w/qmt-mcp/compare/v0.3.0...v0.3.1
[0.4.0]: https://github.com/juju-w/qmt-mcp/compare/v0.3.1...v0.4.0
[0.4.1]: https://github.com/juju-w/qmt-mcp/compare/v0.4.0...v0.4.1
[0.4.2]: https://github.com/juju-w/qmt-mcp/compare/v0.4.1...v0.4.2
[0.4.3]: https://github.com/juju-w/qmt-mcp/compare/v0.4.2...v0.4.3
[0.5.0]: https://github.com/juju-w/qmt-mcp/compare/v0.4.3...v0.5.0
[0.6.0]: https://github.com/juju-w/qmt-mcp/compare/v0.5.0...v0.6.0
[0.7.0]: https://github.com/juju-w/qmt-mcp/compare/v0.6.0...v0.7.0
[0.8.0]: https://github.com/juju-w/qmt-mcp/compare/v0.7.0...v0.8.0
[0.9.0]: https://github.com/juju-w/qmt-mcp/compare/v0.8.0...v0.9.0
[0.10.0]: https://github.com/juju-w/qmt-mcp/compare/v0.9.0...v0.10.0
[0.11.0]: https://github.com/juju-w/qmt-mcp/compare/v0.10.0...v0.11.0
[0.11.1]: https://github.com/juju-w/qmt-mcp/compare/v0.11.0...v0.11.1
[0.12.0]: https://github.com/juju-w/qmt-mcp/compare/v0.11.1...v0.12.0
[0.12.1]: https://github.com/juju-w/qmt-mcp/compare/v0.12.0...v0.12.1
[0.13.0]: https://github.com/juju-w/qmt-mcp/compare/v0.12.1...v0.13.0
[0.13.1]: https://github.com/juju-w/qmt-mcp/compare/v0.13.0...v0.13.1
[0.14.0]: https://github.com/juju-w/qmt-mcp/compare/v0.13.1...v0.14.0
[0.14.1]: https://github.com/juju-w/qmt-mcp/compare/v0.14.0...v0.14.1
[0.14.2]: https://github.com/juju-w/qmt-mcp/compare/v0.14.1...v0.14.2
[0.14.3]: https://github.com/juju-w/qmt-mcp/compare/v0.14.2...v0.14.3
[0.14.4]: https://github.com/juju-w/qmt-mcp/compare/v0.14.3...v0.14.4
