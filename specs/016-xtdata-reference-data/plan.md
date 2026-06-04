# Implementation Plan: xtdata Reference Data

**Branch**: `016-xtdata-reference-data` | **Spec**:
`specs/016-xtdata-reference-data/spec.md`

## Summary

Implement the optional read-only xtdata reference-data tools deferred from 003:
financial data, financial downloads, dividend factors, IPO info, CB metadata,
ETF metadata, period list, holidays refresh, and historical-contract refresh.

## Technical Context

**Language/Version**: Python 3.12 for MCP; Go 1.22 for qmtctl.

**Primary Dependencies**: existing xtdata tool registry, worker pool,
serializers, validation helpers, official `xtdata.get_financial_data`,
`download_financial_data`, `download_financial_data2`, `get_divid_factors`,
`get_ipo_info`, `download_cb_data`, `get_cb_info`, `download_etf_info`,
`get_etf_info`, `download_holiday_data`, `download_history_contracts`,
`get_period_list`.

**Testing**: pytest with fake xtquant; qmtctl command mapping tests; optional
NAS/manual smoke when broker pack supports reference APIs.

**Constraints**:

- Read-only only.
- Capability-gated optional APIs.
- Bounded code/date/table/output fanout.
- No account-scoped IPO actions.

## Project Structure

```text
appliance/mcp/qmt_mcp_xtdata/
├── reference_tools.py        # NEW: financial/IPO/CB/ETF/dividend tools
├── reference_serializers.py  # NEW: DataFrame/dict/list normalization
├── tools.py                  # EDIT: register reference tools
└── validation.py             # EDIT: reference-data validators

appliance/mcp/tests/unit/
├── test_xtdata_reference_tools.py
└── test_reference_serializers.py

cli/qmtctl/internal/qmtctl/
├── cli.go                    # EDIT: ref commands
└── cli_test.go               # EDIT: command mappings
```

## Design Decisions

### Capability Gating

Probe functions lazily at call time through the existing `_call_xtdata` helper.
Missing optional functions return structured `not_supported`/dependency
diagnostics rather than hiding the whole xtdata family.

### Financial Serialization

Normalize `dict[code][table] -> DataFrame` into grouped rows:

```json
{
  "code": "600000.SH",
  "table": "Income",
  "rows": [{"m_anntime": "20240328", "revenue": 123.0}]
}
```

Keep raw row counts and truncation metadata but do not log rows to audit.

### IPO Data Split

Keep xtdata IPO reference data separate from existing xttrade IPO tools:

- xtdata: date-range new-share reference data.
- xttrade: account-side purchase limits and today's broker query data.

## Implementation Phases

1. Validators for financial tables, report type, date ranges, and output bounds.
2. Serializers for DataFrame/dict/list results from financial, IPO, CB, ETF, and
   dividend APIs.
3. MCP tools and capability diagnostics.
4. qmtctl `ref` command group.
5. Tests and optional NAS/manual smoke.

## Risks

- Optional APIs vary by xtquant version. Mitigate with granular capability
  diagnostics.
- Financial data can be large. Mitigate with code/table/date/output bounds and
  clear truncation metadata.
- Some download calls may take time. Keep them worker-backed with separate
  status responses.
