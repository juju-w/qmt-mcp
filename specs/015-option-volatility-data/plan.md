# Implementation Plan: Option Chain & Volatility Inputs

**Branch**: `015-option-volatility-data` | **Spec**:
`specs/015-option-volatility-data/spec.md`

## Summary

Implement a read-only option-data MCP tool family around official xtdata option
APIs. The feature exposes option underlyings, chains, contract detail, quotes,
IV, and volatility-index input packages for external calculators. It reuses 003
snapshot/full-tick serialization and can use 013 quote cache for low-latency
option quote reads.

## Technical Context

**Language/Version**: Python 3.12 for MCP; Go 1.22 for qmtctl.

**Primary Dependencies**: existing xtdata connector/tools, serializers,
validators, worker pool, official `xtdata.get_option_undl_data`,
`xtdata.get_option_list`, `xtdata.get_option_detail_data`, optional
`xtdata.get_option_iv`, optional BSM helpers, optional 013 quote cache.

**Testing**: pytest unit tests with fake xtquant option APIs; Go qmtctl mapping
tests; NAS/manual smoke with real option entitlement if available.

**Constraints**:

- Read-only only.
- Capability gated: missing option APIs produce not-supported diagnostics.
- Bounded fanout for chain and quote requests.
- No raw tick retention and no VIX value publication in v1.

## Project Structure

```text
appliance/mcp/qmt_mcp_xtdata/
├── option_tools.py          # NEW: option MCP tools
├── option_serializers.py    # NEW: option detail/chain/quote normalization
├── option_aliases.py        # NEW: family aliases and validation helpers
├── tools.py                 # EDIT: register option tools
└── validation.py            # EDIT: option request bounds

appliance/mcp/tests/unit/
├── test_xtdata_option_tools.py
├── test_option_serializers.py
└── test_option_vix_inputs.py

cli/qmtctl/internal/qmtctl/
├── cli.go                   # EDIT: option commands
└── cli_test.go              # EDIT: command-to-tool mapping tests
```

## Design Decisions

### API Preference

Use official option APIs directly:

- `get_option_undl_data` for available underlyings or chains by underlying.
- `get_option_list` for expiry/type filtered chain retrieval.
- `get_option_detail_data` for strike, expiry, call/put, unit, risk-free rate,
  and historical volatility.
- `get_option_iv` only when present and authorized.

Fallback to sector-list discovery only when direct option APIs are unavailable
and capability detection marks the fallback path as enabled.

### Quote Source

Use `qmt_xtdata_snapshot`/full-tick for option contract quotes, with
`quote_policy=prefer_cache|live|cache_only` mirroring portfolio analysis. When
013 has subscribed option contracts, use cache metadata in the response.

### Volatility-Index Inputs

Return a normalized input package for an external VIX service:

- resolved family/underlying;
- underlying quote;
- eligible expiries and days to expiry;
- strike rows with CALL/PUT detail and quote midpoint fields;
- risk-free-rate fields when available;
- data-quality diagnostics.

Do not calculate the final index value until a later spec defines the exact
formula, source-of-truth test vectors, and rounding rules.

## Implementation Phases

1. Capability detection and validators for option functions, aliases, expiry
   formats, option types, and request fanout.
2. Option serializers for detail, chain grouping, quote rows, and volatility
   input rows.
3. MCP tools for underlyings, chain, detail, quotes, IV, and VIX input packages.
4. qmtctl option commands and JSON output.
5. Tests with fake option APIs and fallback/not-supported cases.
6. NAS/manual smoke against real QMT option data if entitlement is available.

## Risks

- Broker packs may expose different option APIs or require additional market-data
  entitlement. Mitigate with capability detection and clear not-supported
  diagnostics.
- Option chains can be large. Mitigate with max expiry/contract/quote fanout and
  explicit truncation metadata.
- VIX family naming can be ambiguous. Mitigate by returning resolved underlyings
  and allowing explicit underlying codes.
