# Feature Specification: Formula & Factor Runtime

**Status**: Draft
**Depends on**: 003 (bars/downloads), 007 (qmtctl CLI), 012 (optional DB),
013 (quote subscriptions, optional), 015 (option/VIX inputs, related).

## Summary

Expose a controlled MCP runtime for official xtdata formula/model APIs:
`call_formula`, `call_formula_batch`, `subscribe_formula`, and
`generate_index_data`. The goal is to let agents run approved QMT/VBA formulas
or factor models for research and derived datasets, including future VIX/factor
workflows, without giving arbitrary model execution or file-system write access.

This is not a trading feature. It must not submit orders or execute arbitrary
Python. It only calls existing formulas already installed in the QMT/投研端
environment and only when the server-side allowlist permits the formula and
parameters.

## User Scenarios

### US1 - Call an approved formula once (P1)

**Acceptance**: Given formula runtime is enabled and `VIX_INPUT_HELPER` is on the
allowlist, when an agent calls it for `510300.SH` over a bounded date range, then
the tool returns JSON-clean timelist/output arrays with formula provenance.

### US2 - Batch formula calls for a bounded universe (P1)

**Acceptance**: Given a formula and bounded stock list, when an agent requests a
batch call, then the runtime validates all codes, parameters, and output limits,
then returns one result object per code with partial diagnostics.

### US3 - Generate local factor data safely (P2)

**Acceptance**: Given an allowlisted formula and output path policy, when an
operator requests factor generation, then the runtime writes only under the
configured sandbox path, returns status/metadata, and never allows arbitrary
paths outside the sandbox.

### US4 - Subscribe to formula output for cache updates (P2)

**Acceptance**: Given subscription mode is enabled, when an operator subscribes
to an approved formula, the runtime stores the subscription id, normalizes
callback updates into a bounded cache, and can unsubscribe cleanly.

### US5 - qmtctl workflow (P2)

**Acceptance**: `qmtctl formula call`, `qmtctl formula batch`,
`qmtctl formula generate`, `qmtctl formula subscribe`, and
`qmtctl formula unsubscribe` support readable summaries and full JSON output.

## Functional Requirements

- **FR-001**: Formula runtime MUST be disabled by default and require explicit
  server config such as `QMT_ENABLE_FORMULA_RUNTIME=1`.
- **FR-002**: Formula execution MUST be restricted to a server-side allowlist of
  formula names and parameter schemas. Clients cannot add allowlist entries.
- **FR-003**: Add MCP tools:
  `qmt_xtdata_formula_call`, `qmt_xtdata_formula_call_batch`,
  `qmt_xtdata_formula_generate_factor`,
  `qmt_xtdata_formula_subscribe`, `qmt_xtdata_formula_unsubscribe`,
  `qmt_xtdata_formula_subscriptions`, and `qmt_xtdata_formula_cache`.
- **FR-004**: All calls MUST validate formula name, stock codes, period, date
  range, count, dividend type, parameter schema, max output points, and timeout
  before calling xtdata.
- **FR-005**: `generate_index_data` MUST restrict `result_path` to a configured
  sandbox directory and return metadata/status instead of reading arbitrary local
  files by default.
- **FR-006**: `subscribe_formula` MUST store official subscription ids and MUST
  call `unsubscribe_formula` when disabled/removed.
- **FR-007**: Formula callback/cache storage MUST be bounded and latest-only by
  default, unless a future spec defines historical retention.
- **FR-008**: Runtime capability detection MUST report formula support, factor
  generation support, subscription support, sandbox path, and allowlisted formula
  names or safe aliases.
- **FR-009**: All formula calls MUST be worker-backed and audited with formula
  name, code count, date range, parameter keys, output size, and status. Raw
  large outputs SHOULD NOT be written to audit logs.
- **FR-010**: qmtctl MUST expose formula commands and disabled/refused responses.
- **FR-011**: The feature MUST NOT execute arbitrary Python code, create formulas,
  modify formulas, trade, or bypass MCP account/market-data allowlists.

## Formula Policy

Each allowlisted formula has:

- `alias`: optional external name.
- `formula_name`: real QMT formula/model name.
- `allowed_periods`.
- `max_codes`, `max_count`, `max_days`, `max_outputs`.
- `param_schema`: allowed keys, types, defaults, and bounds.
- `allow_generate`: whether factor-file generation is allowed.
- `allow_subscribe`: whether formula subscription is allowed.

## Success Criteria

- **SC-001**: With runtime disabled, formula tools refuse before xtdata calls.
- **SC-002**: Fake xtdata tests cover allowed call, refused formula, bad params,
  oversized output, batch partial diagnostics, and sandboxed generation.
- **SC-003**: Subscription tests verify callback cache updates and
  `unsubscribe_formula` cleanup.
- **SC-004**: qmtctl formula commands map to MCP tools and support JSON output.
- **SC-005**: Existing market-data and option tools work unchanged when formula
  runtime is disabled.

## Out of Scope

- Creating, editing, importing, or deleting formulas.
- Arbitrary Python or shell execution.
- Trading/order placement.
- Publishing a repo-owned VIX value without a separate formula/rounding/test
  vector spec.
- Unbounded factor warehouses or unrestricted local file reads.

## Assumptions

- Formula/model APIs require a QMT 投研端 or compatible environment; many broker
  packs may not support them.
- VIX work should use 015 for raw option/VIX input data first; formula runtime is
  an optional execution path for existing QMT-side models or derived factors.
