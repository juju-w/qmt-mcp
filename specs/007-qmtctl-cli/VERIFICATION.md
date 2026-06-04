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
