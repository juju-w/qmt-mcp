# Feature Specification: qmtctl CLI Client

**Status**: Draft
**Depends on**: 002 (MCP core streamable-http), 003 (market data), 006 (instrument search)

## Summary

Provide `qmtctl`, a compiled command-line client for humans, scripts, CI smoke
checks, and simple agent shell usage. The CLI is a thin client over the
appliance's streamable-http MCP endpoint. It MUST NOT import `xtquant` locally
or duplicate QMT business logic.

Recommended implementation language: **Go**.

Rationale: Go gives simple static/single-binary distribution, easy
cross-compilation for Linux/macOS/Windows, strong HTTP/JSON support, and fast
iteration. Rust is acceptable later for a hardened rewrite, but Go is the best
first compiled distribution target.

## Connection Model

Default environment:

```text
QMT_MCP_URL=http://127.0.0.1:8765/mcp
QMT_MCP_TOKEN=...
```

All business commands call MCP tools over streamable HTTP. `/healthz` may be
used directly only for lightweight health checks.

## Proposed Commands

```bash
qmtctl health
qmtctl tools
qmtctl search 天岳
qmtctl resolve 纳指 --rank liquidity
qmtctl snapshot 510300.SH
qmtctl bars 510300.SH --period 1d --start 20250101 --end 20250110
qmtctl cache status
qmtctl cache refresh
qmtctl smoke
```

Global flags:

```text
--url
--token
--json
--timeout
--verbose
```

## Functional Requirements

- **FR-001**: The CLI MUST be distributed as a compiled binary without requiring
  Python or Node on the user's machine.
- **FR-002**: The CLI MUST call the MCP streamable-http endpoint by default and
  use bearer-token auth.
- **FR-003**: The CLI MUST support human-readable output and `--json` machine
  output.
- **FR-004**: The CLI MUST wrap common MCP tools without reimplementing QMT
  SDK behavior locally.
- **FR-005**: The CLI MUST include a `smoke` command that validates health,
  tool discovery, instrument search, and one safe xtdata read path when ready.
- **FR-006**: Errors MUST preserve MCP error type/message and exit with
  non-zero status.
- **FR-007**: Secrets MUST NOT be printed in normal or verbose logs.

## Out of Scope

- Direct local Wine/QMT/xtquant integration.
- Order placement or trading commands.
- Replacing MCP as the main integration surface.

## Success Criteria

- **SC-001**: A user can download one binary and run `qmtctl health` against a
  running appliance.
- **SC-002**: `qmtctl resolve 纳指 --rank liquidity --json` returns the same
  structured payload as the MCP tool.
- **SC-003**: `qmtctl smoke` returns a useful diagnosis for auth failure,
  MCP-down, xtdata-not-ready, and successful xtdata-ready states.
