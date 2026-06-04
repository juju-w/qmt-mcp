# Implementation Plan: Custom Sector Management

**Branch**: `017-custom-sector-management` | **Spec**:
`specs/017-custom-sector-management/spec.md`

## Summary

Implement explicitly enabled QMT custom sector management through official xtdata
sector mutation APIs. The feature is separated from read-only sector listing and
constituent tools because it changes local QMT state.

## Technical Context

**Language/Version**: Python 3.12 for MCP; Go 1.22 for qmtctl.

**Primary Dependencies**: existing xtdata connector, validation helpers, audit,
health/capability reporting, official `xtdata.create_sector_folder`,
`create_sector`, `add_sector`, `remove_stock_from_sector`, and optional delete/
reset functions when present.

**Testing**: pytest with fake xtdata mutation functions; qmtctl mapping tests;
manual smoke only against an isolated `MCP/` test prefix.

**Constraints**:

- Disabled by default.
- Prefix-limited.
- Confirmation required for destructive operations.
- No mutation of built-in sectors.

## Project Structure

```text
appliance/mcp/qmt_mcp_xtdata/
├── sector_write_tools.py    # NEW: gated custom sector mutation tools
├── sector_policy.py         # NEW: prefix/confirmation/capability policy
├── tools.py                 # EDIT: optional registration behind config flag
└── validation.py            # EDIT: sector-name and code-count validators

appliance/mcp/tests/unit/
├── test_sector_policy.py
└── test_xtdata_sector_write_tools.py

cli/qmtctl/internal/qmtctl/
├── cli.go                   # EDIT: sector commands
└── cli_test.go              # EDIT: command mappings
```

## Design Decisions

### Separate From Read Tools

Keep `qmt_xtdata_sector_list` and `qmt_xtdata_sector_constituents` always
read-only. Register write tools only when the explicit sector-write flag is on.

### Prefix Guard

Default allowed prefixes: `MCP/`, `AI/`. Operators can override through config,
but empty/unbounded prefix lists are invalid.

### Idempotency

Create/add operations should be idempotent where possible: if the target sector
exists or codes are already present, return `unchanged`/`updated` rather than
failing.

## Implementation Phases

1. Config and policy helpers for enable flag, prefixes, confirmation, and
   capability checks.
2. MCP mutation tools with audit and health updates.
3. qmtctl sector commands.
4. Tests for disabled, allowed, refused, idempotent, and destructive paths.
5. Isolated manual smoke on `MCP/Test`.

## Risks

- A bad tool call could alter user-maintained sectors. Mitigate with disabled
  default, prefix guard, confirmation, and audit.
- Official APIs may differ by xtquant version. Mitigate with capability checks
  and not-supported diagnostics.
