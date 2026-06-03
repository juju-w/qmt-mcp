# Implementation Plan: Production MCP Server Core

**Branch**: `002-mcp-server-core` | **Date**: 2026-06-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-mcp-server-core/spec.md`

## Summary

Replace the vendored pass-through MCP launcher with a production MCP core that
keeps the appliance safe and observable: bearer auth, explicit tool registry,
capability-gated tool families, stable health/capabilities surfaces, uniform
error envelopes, worker-backed blocking calls, and append-only audit logging.
Feature 002 does **not** implement the xtdata catalog itself; it creates the
framework that feature 003 plugs into. Postgres is intentionally not mandatory:
JSONL audit is the default sink and database persistence is deferred.

## Technical Context

**Language/Version**: Windows Python 3.12 inside Wine for the MCP runtime; Bash for launch scripts.

**Primary Dependencies**: `fastmcp`, `uvicorn`, Python standard library (`asyncio`, `concurrent.futures`, `json`, `logging`), and the broker pack's `xtquant` only for runtime capability checks.

**Storage**: Append-only JSONL audit file by default. No required database. Optional Postgres is deferred to a later persistence/observability feature.

**Testing**: Build/runtime smoke tests using Wine Python; HTTP/MCP contract checks for auth, health, capabilities, audit, tool discovery, and simulated worker-backed slow tools.

**Target Platform**: Native linux/amd64 host running the Wine-based QMT appliance container. Apple Silicon remains emulation-only and not a validation target.

**Project Type**: Containerized local MCP service inside `qmt-wine-rdp/`.

**Performance Goals**: Health/capability checks remain responsive while at least one blocking worker call is running; concurrency limit prevents unbounded QMT/xtquant calls.

**Constraints**: Fail closed on missing external auth token, never expose write/trade tools, never log secrets, never register dependency tools by accident, do not require a logged-in QMT session for MCP core startup.

**Scale/Scope**: One MCP service per appliance instance; one broker pack per instance; first real tool family is xtdata in feature 003.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Broker-Agnostic Base | MCP consumes resolved config from mounted broker pack; no broker data is baked into the image | PASS |
| II. Read-Only by Default | Core exposes no write tools; `mcp.mode: trade` remains future-only | PASS |
| III. Reproducible / Native / Pinned | Runtime stays in declared Wine Python/base image; no hand-mutated service state | PASS |
| IV. Contract-First MCP | Tools require explicit schemas, allow-listing, error envelopes, and capability states | PASS |
| V. Observable / Auditable / Readiness-Gated | Health/capability surfaces and audit logging are first-class | PASS |
| VI. Security by Default | Bearer auth required externally; secrets excluded from logs/audit | PASS |
| VII. Spec-Driven | 002 is scoped to MCP core; 003/004/005 remain separate features | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/002-mcp-server-core/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── tool-catalog.md
│   ├── health.md
│   └── audit.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
qmt-wine-rdp/
├── mcp/
│   ├── qmt_mcp.py              # replace pass-through launcher with core app
│   └── qmt_mcp_core/           # new internal package for auth/registry/health/audit
├── scripts/
│   └── start-mcp.sh            # pass env + launch core
└── Dockerfile                  # build-time smoke for core import/tool filtering
```

**Structure Decision**: Keep the MCP core under `qmt-wine-rdp/mcp/` so it remains
packaged with the appliance. Add an internal package rather than growing the
single launcher file; keep `qmt_mcp.py` as the executable entrypoint for Wine.

## Complexity Tracking

> Not required — Constitution Check passed with no violations.
