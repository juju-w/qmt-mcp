# Implementation Plan: Account-Query Tools (xttrade, read-only)

**Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

## Summary

Add an **opt-in, read-only** `xttrade_query` tool family that wraps `xttrader`
account queries (asset, positions, orders, trades, ...) as structured MCP tools.
Off by default; enabled only with an explicit flag **and** a server-side account
allowlist. Reuses the 005 trader connector for the session: when 004 is enabled it
supplies the real `xttrader` connect handshake to the connector; tools are
readiness-gated and refuse cleanly with `trader-not-ready` / `not_authorized`.
**No** order/cancel/transfer/borrow/export tools — ever (asserted).

Because broker programmatic permission is not available to the maintainer, only
the disabled / not-authorized / not-ready / validation boundaries are testable
here; the success paths (real query payloads) need a permissioned account and are
left for a community PR. The SDK-call code is written to the documented xttrader
interface but marked unverified.

## Technical Context

**Language/Version**: Windows Python 3.12 (Wine) at runtime; pure-logic modules host-testable.
**Primary Dependencies**: broker pack's `xtquant.xttrader` / `xttype` (lazy, runtime only); reuses `qmt_mcp_core` registry/health/audit/workers + the 005 `TraderConnector`.
**Testing**: host unit tests for account allowlist/type validation, serializers (fake SDK objects), and gating; SDK calls validated only on a permissioned amd64 host.
**Constraints**: read-only only; allowlist enforced server-side (agent cannot widen via args, fail-closed); no raw SDK object passthrough; every query audited; never expose the family by merely installing the package.

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| I. Broker-Agnostic | xttrader/xttype come from the pack; nothing baked | PASS |
| II. Read-Only by Default | family off by default; ONLY query_* tools; `assert_no_write_tools` covers it | PASS |
| III. Reproducible | no new pinned deps; runtime SDK from pack | PASS |
| IV. Contract-First | typed inputs, account enum, structured outputs (no raw passthrough), rich docstrings | PASS |
| V. Observable / Readiness-Gated | readiness-gated; per-query audit; health family state | PASS |
| VI. Security | enable-flag + allowlist; fail-closed; no secrets; account ids validated | PASS |
| VII. Spec-Driven | scoped to read-only queries; writes remain a separate future guarded feature | PASS |

## Project Structure

```text
appliance/mcp/
├── qmt_mcp_xttrade/
│   ├── __init__.py
│   ├── accounts.py      # account-type enum, id validation, server-side allowlist
│   ├── serializers.py   # XtAsset/XtPosition/XtOrder/XtTrade -> structured dicts (+ raw m_* dump)
│   ├── session.py       # TraderSession: real xttrader connect (connector connect_fn) + query()
│   └── tools.py         # register read-only query tools (gated, readiness-aware, audited)
└── qmt_mcp_core/
    ├── config.py        # QMT_ENABLE_XTTRADE_QUERY (off), QMT_TRADE_ACCOUNTS, QMT_TRADE_ACCOUNT_TYPE
    ├── health.py        # xttrade_query family state transitions
    └── app.py           # register_optional_xttrade(...); wire session.connect into the connector
```

**Structure Decision**: Mirror the `qmt_mcp_xtdata` layout. Pure logic (accounts,
serializers) is import-light and unit-tested on host; `session.py` is the only
module that touches `xttrader` (lazily), so the rest stays testable.

## Complexity Tracking

> Not required — Constitution Check passed.
