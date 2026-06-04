# Implementation Plan: Portfolio Risk Analysis

**Branch**: `014-portfolio-risk-analysis` | **Spec**: `specs/014-portfolio-risk-analysis/spec.md`

## Summary

Build read-only portfolio analysis on top of existing xttrade account-query tools
and xtdata market data. The implementation should keep calculation logic pure and
unit-testable, register a small MCP tool family for summaries/exposures/risk
checks, and add qmtctl commands for operator use.

Do not implement the core as a Codex skill. Skills can be added later as a
presentation/explanation wrapper over `qmt_portfolio_*` outputs, but the secure
data access and calculations belong in the MCP service.

## Technical Context

**Language/Version**: Python 3.12 for MCP; Go 1.22 for qmtctl.

**Primary Dependencies**: 004 xttrade session/tools/serializers, 003 xtdata
snapshot/bars, 006 search cache metadata, optional 013 quote cache, optional 012
DB warehouse for historical bars.

**Storage**: None required for v1. Optional future storage may cache analysis
events or risk-check results, but the first version computes on demand.

**Testing**: pytest unit tests for pure calculations and tool gating; Go tests for
qmtctl command mapping; optional NAS smoke when account-query permission exists.

**Target Platform**: QMT MCP appliance and qmtctl CLI.

**Performance Goals**: Portfolio summary for up to 100 positions should complete
within 2 seconds with cached quotes and within existing worker timeouts with live
xtdata. Pure calculation should be sub-100 ms.

**Constraints**:

- Read-only.
- Account allowlist enforced server-side.
- No silent zero valuation for missing quotes.
- Outputs must include calculation/freshness metadata.

**Scale/Scope**: Small to medium retail/pro account portfolios first: up to 100
positions by default. Larger portfolios should work with explicit limits and may
return partial diagnostics if quote coverage is incomplete.

## Project Structure

```text
appliance/mcp/qmt_mcp_portfolio/       # NEW
├── __init__.py
├── calculations.py                    # pure metrics/exposure/risk checks
├── models.py                          # typed dict/dataclass helpers if useful
├── tools.py                           # MCP registration, gating, orchestration
└── thresholds.py                      # defaults + validation

appliance/mcp/qmt_mcp_core/app.py      # EDIT: optional portfolio registration
appliance/mcp/qmt_mcp_core/health.py   # EDIT: portfolio family capability state

appliance/mcp/tests/unit/
├── test_portfolio_calculations.py     # NEW
├── test_portfolio_thresholds.py       # NEW
└── test_portfolio_tools.py            # NEW

cli/qmtctl/internal/qmtctl/
├── cli.go                             # EDIT: portfolio commands
├── cli_test.go                        # EDIT: command mapping tests
└── format.go                          # EDIT: summary/exposure display keys
```

## Design Decisions

### MCP Tools, Not Skill

Portfolio analysis needs real account data, server-side allowlist enforcement,
audit logging, and consistent quote sourcing. Those boundaries are already in
the MCP appliance, so 014 is a service-side tool family. A skill can later call
these tools to produce a narrative report, but it must not bypass the MCP tools
or duplicate their calculations.

### Separate Package

Use a new `qmt_mcp_portfolio` package rather than folding analysis into xttrade
or xtdata. This keeps raw data adapters separate from derived analytics and makes
pure calculations easy to test without QMT.

### Orchestration Flow

1. Validate account id through existing 004 allowlist/session boundaries.
2. Query asset and positions via 004 read-only paths.
3. Fetch quotes for position codes using quote policy:
   `prefer_cache`, `live`, or `cache_only`.
4. Enrich metadata from 006 cache when available.
5. Run pure calculations.
6. Return metrics plus partial-data diagnostics.

### Tool Surface

- `qmt_portfolio_summary`: account-level headline metrics, top positions, quote
  coverage, and diagnostics.
- `qmt_portfolio_positions`: enriched position table with weights/P&L.
- `qmt_portfolio_exposure`: grouped exposure by market/type/sector where
  available.
- `qmt_portfolio_risk_checks`: threshold-based checks and warnings.

### Risk Check Defaults

Initial defaults should be conservative but configurable:

- max single position weight: 30%
- max top 5 weight: 70%
- min cash ratio: 5%
- max stale quote age: 30 seconds when using cache
- min quote coverage: 95%

These are operational guardrails, not trading advice.

### Capability State

Portfolio family states:

- `disabled`: feature flag off.
- `not_authorized`: xttrade query unavailable/not authorized.
- `not_ready`: trader or xtdata not ready.
- `enabled`: all required paths available.
- `degraded`: usable but missing metadata, stale quotes, or partial quote
  coverage.

## Implementation Phases

1. Pure calculation layer: position valuation, weights, concentration, exposure,
   risk thresholds.
2. Tool orchestration and gating: compose xttrade/xtdata/metadata sources.
3. Health/capabilities integration.
4. qmtctl portfolio commands.
5. Tests and NAS/manual verification.

## Risks

- Brokers expose slightly different cost/market-value fields. Mitigate by using
  serializers defensively and reporting unavailable metrics explicitly.
- Quote timing can make values drift. Mitigate with quote timestamps and
  freshness metadata.
- Sector metadata may be incomplete. Treat sector exposure as best-effort and
  include partial-data notes.

## Constitution Check

Passes:

- read-only only;
- server-side account allowlist;
- no secrets in output/audit;
- pure logic host-testable;
- degraded states are explicit;
- no order/trading tool exposure.
