# Implementation Plan: Formula & Factor Runtime

**Branch**: `018-formula-factor-runtime` | **Spec**:
`specs/018-formula-factor-runtime/spec.md`

## Summary

Implement a disabled-by-default, allowlisted runtime for official xtdata
formula/model APIs. The runtime supports one-shot calls, bounded batch calls,
sandboxed factor generation, and optional formula subscriptions with latest-only
cache updates.

## Technical Context

**Language/Version**: Python 3.12 for MCP; Go 1.22 for qmtctl.

**Primary Dependencies**: existing worker/audit/config/health infrastructure,
official `xtdata.call_formula`, `call_formula_batch`, `subscribe_formula`,
`unsubscribe_formula`, and `generate_index_data`.

**Testing**: pytest with fake xtdata formula functions; qmtctl mapping tests;
NAS/manual smoke only if a 投研端 formula environment is available.

**Constraints**:

- Disabled by default.
- Server-side formula allowlist and parameter schemas.
- Sandboxed output path for generated factor files.
- No arbitrary Python, formula editing, or trading.

## Project Structure

```text
appliance/mcp/qmt_mcp_xtdata/
├── formula_policy.py       # NEW: allowlist and parameter validation
├── formula_tools.py        # NEW: call/batch/generate/subscribe tools
├── formula_cache.py        # NEW: latest-only callback cache
├── tools.py                # EDIT: optional formula registration
└── validation.py           # EDIT: formula request validators

appliance/mcp/tests/unit/
├── test_formula_policy.py
├── test_xtdata_formula_tools.py
└── test_formula_cache.py

cli/qmtctl/internal/qmtctl/
├── cli.go                  # EDIT: formula commands
└── cli_test.go             # EDIT: command mappings
```

## Design Decisions

### Allowlist First

Never expose raw formula names directly unless they are present in server config.
Agents call aliases or allowed names; server maps them to real QMT formula names
and validates parameters against schemas.

### Output Boundaries

Formula outputs can be large. Each formula policy declares max timelist/output
lengths. Responses include truncation metadata if allowed; otherwise oversized
outputs fail with a clear validation/dependency error.

### Factor File Sandbox

`generate_index_data` writes only below a configured directory, for example
`/broker/formula-output`. The MCP tool returns generated file metadata and does
not expose arbitrary file reads in v1.

### Relationship To VIX

Keep 015 as the canonical raw option/VIX input provider. Use 018 to run existing
QMT-side VIX/factor formulas when they are explicitly allowlisted and tested.

## Implementation Phases

1. Config model and allowlist schema.
2. Formula policy validators and output serializers.
3. MCP call/batch/generate tools.
4. Optional formula subscription lifecycle and cache.
5. qmtctl formula commands.
6. Tests and gated manual smoke.

## Risks

- Formula APIs may require 投研端 support. Mitigate with disabled defaults and
  capability diagnostics.
- Model output can be large or slow. Mitigate with worker-backed execution,
  bounds, and timeouts.
- `generate_index_data` writes files. Mitigate with sandboxed paths and no
  arbitrary file readback.
