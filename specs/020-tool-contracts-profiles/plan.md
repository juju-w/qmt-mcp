# Implementation Plan: Tool Contracts and Profiles

**Branch**: `codex/020-tool-contracts` | **Date**: 2026-07-31 |
**Spec**: `specs/020-tool-contracts-profiles/spec.md`

## Summary

Centralize standard tool metadata and result adaptation in `ToolRegistry`.
Introduce a startup visibility policy configured by profile and glob filters,
annotate existing mutation tools explicitly, and test the resulting wire
contracts through modern and legacy MCP paths.

## Technical Context

**Language/Version**: Python 3.12, official MCP Python SDK 2.0.0, Pydantic
provided by the locked MCP runtime.

**Storage**: None.

**Testing**: dependency-light pytest unit tier, official-SDK integration tests,
existing Go regression, official conformance, actionlint, native amd64 image
build.

**Constraints**:

- The unit tier must still import registry/config without installing MCP.
- No tool business payload or input argument may change.
- Default `full` profile preserves the v0.5.0 tool surface.
- Profile filtering is startup-static; request scopes arrive in 021.

## Constitution Check

- **I Broker-agnostic**: PASS. Policy and contracts contain no broker data.
- **II Read-only default**: PASS. Side effects become more accurately labeled;
  no new mutation is added.
- **III Reproducible builds**: PASS. No new dependency is required.
- **IV Contract-first MCP**: PASS. This feature directly strengthens schemas
  and explicit metadata.
- **V Observable/readiness-gated**: PASS. Profile appears in capabilities;
  readiness behavior is unchanged.
- **VI Security by default**: PASS. Profiles reduce callable surface and fail
  closed on invalid configuration.
- **VII Spec-driven delivery**: PASS.

## Project Structure

```text
specs/020-tool-contracts-profiles/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
├── quickstart.md
├── VERIFICATION.md
├── contracts/
│   └── tool-contract.md
└── checklists/
    └── requirements.md

appliance/mcp/qmt_mcp_core/
├── config.py
├── registry.py
└── tool_contracts.py
```

## Implementation Phases

1. Add profile parsing, validation, and pure visibility tests.
2. Add common output model plus MCP result adapter behind lazy SDK imports.
3. Extend registry metadata and mutation annotation safeguards.
4. Mark every existing mutating/cache-writing registration explicitly.
5. Expose profile summary through `qmt_capabilities`.
6. Add modern and legacy wire tests for metadata, structured results, errors,
   profiles, and hidden tool rejection.
7. Update operator/client docs and run the complete quality gates.

## Complexity Tracking

The MCP adapter and visibility policy remain registry-level abstractions because
they eliminate repeated transport code and enforce one cross-family contract.
No business tool module gains SDK response construction.
