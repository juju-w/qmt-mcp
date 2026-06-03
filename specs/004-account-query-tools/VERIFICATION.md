# 004 Verification

Date: 2026-06-04 · Host: darwin/arm64, Python 3.12.2. Pure logic + gating are
host-tested; the actual xttrader query payloads need a broker-permissioned amd64
account (see below) — this feature is, by design, validated only to the
disabled/not-authorized/not-ready/validation boundary locally.

## Implemented

- `qmt_mcp_xttrade/accounts.py` — `AccountType` (STOCK/CREDIT/FUTURE), account-id
  validation, server-side `Allowlist` (fail-closed; agent cannot widen via args).
- `qmt_mcp_xttrade/serializers.py` — structured asset/position/order/trade/generic
  records + defensive `m_*` raw dump (no raw SDK passthrough).
- `qmt_mcp_xttrade/session.py` — `TraderSession`: lazy xttrader connect handshake
  (connector connect_fn) + read-only `query()` dispatch (refuses trader-not-ready).
- `qmt_mcp_xttrade/tools.py` — 8 read-only tools (`asset`, `positions`, `orders`
  +cancelable, `trades`, `position_statistics`, `account_status`,
  `new_purchase_limit`, `ipo_data`): allowlist-checked, readiness-gated,
  worker-backed, audited, rich docstrings. NO write tools.
- `config.py` — `QMT_ENABLE_XTTRADE_QUERY` (off), `QMT_TRADE_ACCOUNTS`,
  `QMT_TRADE_ACCOUNT_TYPE`. `app.py` — `register_optional_xttrade` (flag+allowlist,
  fail-closed) wires `TraderSession.connect` into the 005 connector; connector now
  auto-starts when 004 is enabled. `qmt-entrypoint.sh` bridges the new env.
- `registry.py` — **fixed a latent bug**: `WRITE_TOOL_KEYWORDS` matched bare
  `order`/`slo`/`compact`/`negotiate`, which would have false-flagged read-only
  listings (`query_stock_orders`) and credit/smt READ queries. Refined to precise
  write verbs (`place_order`, `order_stock`, `passorder`, `cancel`, `transfer`,
  `borrow`, `export`, `buy`, `sell`).

## Results (host)

| Check | Command | Result |
|---|---|---|
| Unit tests | `pytest -m 'not integration'` | ✅ 93 passed (incl. accounts 8 / serializers 5 / gating 3) |
| No-write guarantee | `assert_no_write_tools()` over xttrade family | ✅ passes; `qmt_xttrade_orders` (read) not false-flagged |
| Allowlist fail-closed | unknown account id | ✅ refused (`validation`) |
| Readiness gate | session unconnected | ✅ `trader-not-ready` (`not_ready`) |
| Lint / format | `ruff check` / `ruff format --check` | ✅ clean |

## Needs a broker-permissioned amd64 account (success paths)

Enable `QMT_ENABLE_XTTRADE_QUERY=1` + `QMT_TRADE_ACCOUNTS=<id>` on a host where the
broker has granted programmatic-trading permission (`m_nPythonConnectNet`) and QMT
is logged in, then verify:
- asset/positions/orders/trades return correct structured data (SC-001)
- an account id not on the allowlist is refused 100% of the time (SC-002)
- trader-not-ready degrades cleanly when the session drops (SC-003)
- without permission: `xttrade` → `not_authorized`, server stays healthy (SC-004)

**Unverified here**: the exact xttrader method names / object attribute names. The
serializers read several attribute-name fallbacks and always include the raw `m_*`
dump, so minor SDK naming differences degrade gracefully rather than break — but a
permissioned run should confirm field mappings. PRs welcome (see README Help-wanted).
