# Verification: Intelligent Instrument Screening

**Feature**: 033
**Date**: 2026-08-17
**Status**: Automated, fake-runtime, and read-only Windows QMT verification complete.

## Automated Gates

Run from `appliance/mcp` unless noted otherwise:

| Command | Result |
|---|---|
| `ruff check .` | passed |
| `ruff format --check .` | passed after formatting the new files |
| `pytest -q` | 390 passed, 1 optional PostgreSQL test skipped, 2 dependency deprecation warnings |
| `pytest -q -m 'not integration and not db'` | 329 passed, 61 deselected; PostgreSQL module skipped at collection because `asyncpg` is absent |
| Official-SDK screening/App/Tasks/OAuth integration selection | 52 passed |
| `go test ./...` | passed |
| `go vet ./...` | passed |
| `go build ./...` and `go build ./cmd/conformance` | passed |
| `.github/scripts` unittest discovery | 16 passed |
| `actionlint@v1.7.12` | passed with Go 1.25.13 |
| `git diff --check` | passed |

The local machine has no `dotnet`, so launcher restore/build/test could not run.
The optional PostgreSQL live test could not run because `asyncpg` and a test DSN
are not installed. Neither limitation blocks the dependency-free screening path;
both remain CI/live-delivery checks.

## Deterministic Evidence

- Catalog: all stock/ETF factors remain discoverable with localized labels,
  units, windows, profiles, presets, and runtime availability. P1 benchmark,
  IOPV, and component factors remain explicitly unavailable until both the
  server implementation and broker runtime capability exist.
- ETF universe: strict `csi_500` resolution returns only `510500.SH`,
  `512500.SH`, and `159922.SZ`. S&P 500, technology, and biotech lookalikes are
  removed before liquidity or spread ranking. Provenance is
  `strict-exposure-alias`, and the universe has a stable SHA-256 membership
  digest.
- Stock point-in-time behavior: reports announced after `as_of` are excluded.
  Historical market cap and turnover use the latest `Capital` row announced by
  that date and do not fall back to current shares. ROE uses the comparable
  prior-year report-period equity.
- Stage diagnostics: fixture screens disclose resolved, data-eligible,
  filter-passed, ranked, and returned counts plus daily/snapshot/announced-
  financial source dates.
- Rank reconstruction: every weighted fixture score equals the sum of its
  disclosed contributions. Contributions include raw/winsorized values,
  percentile, requested and effective weights, missing policy, and reason.
- Cache behavior: the first three-code ETF screen reports 0 hits/6 misses; an
  immediate repeat reports 6 hits/0 misses. After five seconds only the three
  snapshot observations expire, while completed-daily observations remain
  cached. Captured explanations use a separate bounded 15-minute result store
  and make zero source calls.
- Degradation: no-DB catalog -> Task screen -> explanation passes through the
  real MCP 2026-07-28 ASGI transport. A missing optional financial rank factor
  receives neutral treatment and 0.5 candidate coverage; hard requirements fail
  before scanning with capability and explicit repair-tool guidance.
- Side effects: call-spy tests observe only `get_market_data_ex`,
  `get_full_tick`, and `get_financial_data`. No download, formula, filesystem,
  external-network, xttrade, order, NumPy, pandas, PostgreSQL migration, CLI, or
  MCP App path was added to feature 033.
- MCP contract: all three tools are visible in full/readonly/market profiles,
  hidden by account/core or deny rules, require `qmt:read` + `qmt:market`, and
  publish typed nested schemas without App metadata. Normal synchronous calls,
  Tasks, cancellation, structured/text output, and audit summaries pass.

## Windows QMT Smoke

The feature source was staged independently at
`%LOCALAPPDATA%\QMT-MCP\smoke\033`; the installed 1.3.0 deployment and port
18765 were not changed. The reusable `windows-live-smoke.py` runner performs no
downloads, QMT process management, xttrade calls, or account access.

The isolated preflight passed on the inspected Windows host with Python 3.11.9
and the broker-provided xtquant package under the installed Guangda QMT client. It
discovered callable daily-bar, snapshot, instrument-detail, and financial-data
interfaces. The runtime catalog consequently reported 11 available ETF factors
and 25 available stock factors.

The first live attempt correctly failed with `无法连接行情服务！` while QMT was
stopped. After the user opened and logged in to QMT, the same isolated runner
connected successfully without starting or restarting the GUI. Two broker SDK
compatibility findings were fixed before the final run:

- This xtdata build exposes the legacy one-argument
  `get_stock_list_in_sector(sector)` signature. The adapter now retries that
  signature only after a positional `TypeError`; readiness and other runtime
  errors are not masked.
- The broker directory contains NumPy 1.19.1 and pandas 0.22.0, which are
  incompatible with the packaged Python 3.11. The MCP runtime now appends the
  xtquant directory after its own NumPy 2.4.6 and pandas 3.0.5 packages instead
  of allowing the broker directory to shadow them.

The final live evidence was:

- Catalog: daily bars, snapshots, instrument details, and financial-data
  methods were callable; 11 ETF and 25 stock factors were available. P1 ETF
  benchmark/IOPV/component factors remained gated.
- Strict ETF universe: `csi_500` resolved exactly `510500.SH`, `512500.SH`, and
  `159922.SZ`, with `strict-exposure-alias` provenance and a stable SHA-256
  digest. The stage counts were 3 resolved, 3 data-eligible, 1 filter-passed, 1
  ranked, and 1 returned because only `510500.SH` had sufficient local 20-day
  history in this smoke set.
- ETF rank: `510500.SH` had a 20-day average amount of CNY 4,385,137,056.55 as
  of 2026-08-14. Its single disclosed contribution was 100.0 and reconstructed
  its 100.0 score. The captured explanation reported `selected`, rank 1, and
  full coverage.
- Cache: the first ETF call had 0 hits and 3 misses; the immediate repeat had 3
  hits and 0 misses. TTL expiry and unknown-expired-ID behavior remain covered
  by deterministic cache/service tests so the live run did not sleep or mutate
  runtime state merely to wait for expiry.
- Narrow stock: exact code `600519.SH` resolved as `non_financial`; the
  point-in-time `listing_days` factor was 9,118 days at 2026-08-14, with one
  resolved/eligible/passed/ranked/returned candidate, full coverage, and a
  captured selected explanation. No golden investment rank is asserted.
- The final run reported no source errors. Its explicit call surface was limited
  to instrument details, exact sector memberships, and market-data reads; there
  were no download, formula, filesystem, account, xttrade, or order calls.

The broker advertises a financial-data method, but the smoke did not download
or manufacture missing local stock history, so an announced-financial live rank
was not asserted. Announcement-time behavior remains covered by deterministic
point-in-time fixtures.

Live ranks are observations, not golden investment recommendations.
