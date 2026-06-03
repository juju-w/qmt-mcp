# Implementation Plan: Market-Data Tools (xtdata)

**Branch**: `003-market-data-tools` | **Date**: 2026-06-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-market-data-tools/spec.md`

## Summary

Implement the first real MCP tool family using official XtQuant `xtdata`
behavior: bounded request/response market-data tools for snapshot, historical
download, bars, instrument metadata, sectors, trading dates, and holidays. The
tools plug into the 002 MCP core registry, worker executor, audit, and uniform
errors. No Postgres and no streaming subscriptions in this feature.

## Technical Context

**Language/Version**: Windows Python 3.12 inside Wine.

**Primary Dependencies**: 002 MCP core package; broker-pack-provided `xtquant.xtdata`; Python serialization helpers for pandas/numpy conversion.

**Storage**: xtdata/QMT local cache only. No Postgres or separate market-data warehouse.

**Testing**: Smoke tests with a logged-in QMT session for snapshot and bounded history; pure validation tests can run without xtdata readiness.

**Target Platform**: Native linux/amd64 QMT appliance container.

**Project Type**: MCP tool family plugin/package under `appliance/mcp/`.

**Performance Goals**: Bounded outputs; history download and data reads run via 002 worker executor; health remains responsive.

**Constraints**: Current permission is xtdata-first; xttrade permission is not assumed. No callback subscription tools. JSON-clean outputs only.

**Scale/Scope**: Small curated tool catalog for one appliance instance and one QMT session.

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| I. Broker-Agnostic Base | xtdata is loaded only from mounted broker pack | PASS |
| II. Read-Only by Default | All tools are read-only market-data/reference operations | PASS |
| III. Reproducible / Native / Pinned | Tool code lives in repo; xtquant supplied by pack | PASS |
| IV. Contract-First MCP | Tools have explicit contracts in `contracts/xtdata-tools.md` | PASS |
| V. Observable / Auditable / Readiness-Gated | Uses 002 health, readiness, worker, and audit mechanisms | PASS |
| VI. Security by Default | No account/trading tools or secrets | PASS |
| VII. Spec-Driven | Scope excludes streaming, database warehousing, and xttrade | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/003-market-data-tools/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── xtdata-tools.md
```

### Source Code (repository root)

```text
appliance/
└── mcp/
    └── qmt_mcp_xtdata/
        ├── __init__.py
        ├── models.py
        ├── validation.py
        ├── serializers.py
        └── tools.py
```

**Structure Decision**: Keep xtdata tools as a separate internal package that
registers into the 002 core. This prevents the core from becoming a market-data
module and makes later xttrade/query tools independently gated.

## Complexity Tracking

> Not required — Constitution Check passed with no violations.
