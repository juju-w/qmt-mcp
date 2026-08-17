# Quickstart: Intelligent Instrument Screening

This document defines the implementation and verification path for feature 033.
It does not assume PostgreSQL, xttrade, an MCP App host, or live trading
permission.

## 1. Host Unit Tier

Run the dependency-light suite from the MCP package:

```bash
cd appliance/mcp
pytest -m 'not integration and not db'
```

The new unit tier uses plain Python fixtures and must cover:

- Factor catalog IDs, profiles, windows, domains, localized descriptions, and
  runtime availability overlays.
- Universe resolution for explicit codes, exact sectors, A-share market, and
  strict ETF exposure aliases.
- Rejection of CSI 500 lookalikes such as S&P 500 and unrelated codes/names
  containing `500`.
- Pure market-factor formulas for return, moving averages, volatility,
  drawdown, amount, turnover, Amihud illiquidity, and relative strength.
- Point-in-time TTM, growth, ROE, PB, earnings yield, margin, cash-flow quality,
  and leverage formulas from normalized financial rows.
- Announcement dates after `as_of`, duplicate/restated rows, zero/sign-changing
  denominators, insufficient history, and malformed source values.
- Filter operators, decimal ratio units, weighted percentiles, winsorization,
  deterministic tie breakers, and all missing policies.
- Bounded factor cache and screen-result TTL/LRU behavior.
- Selected, rejected, missing, stale, and expired explanation paths.

No unit module may import `xtquant`, pandas, NumPy, MCP, or asyncpg.

## 2. MCP Contract Tier

Run integration tests with the official MCP SDK and fake xtdata:

```bash
cd appliance/mcp
pytest -m integration tests/integration/test_screening_tools.py
```

Verify:

1. The three tools list in `full`, `readonly`, and `market` profiles with
   read-only annotations and structured output.
2. They are hidden by `account`, `core`, custom deny rules, or insufficient
   OAuth market scope.
3. Nested filter/rank request objects appear in the generated input schema and
   invalid requests return actionable alternatives.
4. A large `qmt_screen_instruments` call becomes an MCP Task when the client
   declares Tasks and remains a normal tool result for a narrow non-Task call.
5. Text output is concise and matches the structured result rather than dumping
   all candidate observations.
6. Existing search, bars, reference, formula, and K-line App contracts are
   unchanged.

## 3. Deterministic ETF Fixture

The fake universe contains:

```text
510500.SH  中证500ETF南方
512500.SH  中证500ETF华夏
159922.SZ  中证500ETF嘉实
513500.SH  标普500ETF博时
515000.SH  科技ETF
516500.SH  生物科技ETF
```

Call the service/tool with:

```json
{
  "asset_type": "etf",
  "etf_profile": "broad_market_equity",
  "universe": {
    "kind": "exposure",
    "values": ["csi_500"],
    "policy": "require_complete",
    "include_suspended": false
  },
  "preset_id": "etf_execution_quality",
  "limit": 5
}
```

Expected behavior:

- Only the first three instruments enter the resolved universe.
- Membership is established before amount/spread ranking.
- `513500.SH`, `515000.SH`, and `516500.SH` are absent regardless of liquidity.
- Every selected result has `exposure_group=csi_500`, source dates, coverage,
  raw values, and disclosed contributions.
- The returned `screen_id` can explain a selected code and an eligible but
  lower-ranked code without a new xtdata call.

## 4. Deterministic Stock Fixture

Build four groups:

- Ordinary profitable industrial companies.
- Banks, brokers, and insurers.
- Suspended/new/illiquid ordinary companies.
- Companies with financial reports announced before and after the chosen
  `as_of` date.

Call:

```json
{
  "asset_type": "stock",
  "stock_profile": "non_financial",
  "universe": {
    "kind": "sector",
    "values": ["fixture-industry"],
    "policy": "require_complete",
    "include_suspended": false
  },
  "as_of": "20241231",
  "preset_id": "stock_liquid_quality",
  "filters": [
    {
      "factor": {"factor_id": "roe_ttm", "params": {}},
      "operator": "gte",
      "value": 0.10
    }
  ],
  "limit": 20,
  "diagnostics": "detailed"
}
```

Expected behavior:

- Financial companies are excluded or rejected as profile-incompatible before
  ordinary-company fundamentals are calculated.
- The `0.10` threshold is interpreted as 10 percent.
- Reports announced in 2025 cannot affect the 2024-12-31 result.
- Negative prior profit produces `non_comparable_denominator` for growth rather
  than a large synthetic percentage.
- The score equals the displayed sum of contributions within tolerance.

## 5. Missing Capability Fixture

Disable `get_financial_data`, ETF IOPV, or ETF reference methods selectively.

Expected behavior:

- `qmt_factor_catalog` still lists affected definitions as unavailable with
  required capability and reason.
- A hard filter using an unavailable factor fails before scanning.
- An optional rank factor follows the requested missing policy and lowers
  coverage when neutral is explicitly allowed.
- No screen automatically calls `download_financial_data` or
  `download_etf_info`.
- Guidance names the existing explicit download tool when one can repair local
  coverage.

## 6. Live QMT Smoke

Prerequisites:

- QMT is running and logged in.
- xtdata health is ready.
- The 006 instrument cache has a non-seed, non-partial A-share/ETF universe.
- Financial smoke is optional and requires locally downloaded financial tables.

Recommended sequence:

1. Call `qmt_factor_catalog(asset_type="etf")` and record capability states.
2. Screen one known ETF exposure with `etf_execution_quality` and a limit of five.
3. Verify every code belongs to the resolved exposure using instrument names and
   source provenance; do not validate rank from name similarity.
4. Explain the first and last returned candidates and confirm no new source
   timestamp appears.
5. Call a narrow non-financial stock sector screen using only market factors.
6. If financial data is present, add positive earnings yield, ROE, and
   cash-flow-quality filters and inspect announcement dates.
7. Repeat one screen to verify eligible completed-daily cache reuse.
   Confirm `cache.factor_hits` increases, daily source calls do not, and a live
   spread is fetched again after its five-second factor-cache TTL.
8. Wait beyond the screen-result TTL and verify explanation returns an expired
   result error rather than recomputing.

Live results are observations, not golden investment ranks. Verification checks
contract, membership, timestamps, coverage, and deterministic computation.

## 7. Full Quality Gates

```bash
cd appliance/mcp
ruff check .
ruff format --check .
pytest -m 'not integration'

cd ../../cli/qmtctl
go test ./...
go vet ./...
go build ./...
go build ./cmd/conformance

cd ../..
python -m unittest discover -s .github/scripts -p 'test_*.py'
git diff --check
```

No frontend build or Playwright suite is added because feature 033 does not
ship an MCP App.
