# Verification: qmtctl CLI Client

## 2026-06-04 NAS Appliance Smoke

Target: deployed NAS appliance over `http://<nas-host>:18765/mcp`.

The token was loaded from the local git-ignored appliance environment file and
was not printed.

Checks:

- `curl /livez` returned `{"ok": true, "server": "live"}`.
- Authenticated `curl /healthz` returned `transport=streamable-http`,
  `xtdata=ready`, `database=connected`, and QMT login `logged_in`.
- `qmtctl health` returned live server state.
- `qmtctl tools` listed core and xtdata tools.
- `qmtctl smoke --query 纳指 --code 510300.SH` passed health, tool discovery,
  instrument search, and snapshot checks.
- `qmtctl resolve 纳指 --rank liquidity --json` returned ranked ETF candidates.
- `qmtctl snapshot 510300.SH --json` returned one quote snapshot.
- `qmtctl bars 510300.SH --period 1d --count 3 --json` returned OHLC rows from
  `get_market_data_ex`.

## 2026-06-04 CLI Build Matrix

Local verification:

- `go test ./...`
- `go vet ./...`
- `go build ./...`
- Cross-compiled qmtctl for `linux/amd64`, `linux/arm64`, `darwin/amd64`,
  `darwin/arm64`, `windows/amd64`, and `windows/arm64`.

The release workflow uses the same six-target matrix.

## 2026-06-04 xttrade Read-Only CLI Mapping

Host-tested command-to-tool mapping for the 004 read-only account-query family:

- `qmtctl account asset --account <id>` -> `qmt_xttrade_asset`
- `qmtctl account positions --account <id>` -> `qmt_xttrade_positions`
- `qmtctl account orders --account <id> --cancelable-only` -> `qmt_xttrade_orders`
- `qmtctl account trades --account <id>` -> `qmt_xttrade_trades`
- `qmtctl account status --account <id>` -> `qmt_xttrade_account_status`
- `qmtctl account statistics --account <id>` -> `qmt_xttrade_position_statistics`
- `qmtctl account purchase-limit --account <id>` -> `qmt_xttrade_new_purchase_limit`
- `qmtctl account ipo` -> `qmt_xttrade_ipo_data`

The currently deployed NAS appliance reports account-query as disabled, so live
success-path account data was not requested.
