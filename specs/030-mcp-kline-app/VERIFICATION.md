# Verification: Interactive K-Line MCP App

## Local results

Verified on 2026-08-14 from branch `codex/030-mcp-kline-app`.

| Surface | Result |
|---|---|
| Python lint and formatting | `ruff check .` passed; 104 files formatted |
| Python unit tier | 243 passed, 1 PostgreSQL fixture skipped |
| MCP integration tier | 55 passed, including Apps discovery/resource/call and OAuth |
| Frontend | TypeScript passed; Vitest 4 passed; single-file Vite build passed |
| App artifact | 536.84 KB raw / 145.04 KB gzip; standalone load made no external requests |
| Go qmtctl | test, vet, package build, and conformance client build passed |
| Repository policy | 16 Python policy tests, actionlint, and `git diff --check` passed |
| Visual QA | desktop/tablet/mobile, light/dark, zh/en, success/empty/error/retry passed |
| Canvas QA | nontransparent and colored samples confirmed in price and volume panes |

The Mac does not have `dotnet` installed. The configured Windows QMT host was
offline during this pass, so native launcher build and Windows package smoke
are delegated to the required `launcher-core` and `launcher-windows-package`
PR checks.

## Contract evidence

- `server/discover` advertises `io.modelcontextprotocol/ui` only when the chart
  tool is visible and xtdata is enabled.
- `tools/list` publishes `qmt_xtdata_kline_chart` with the versioned
  `ui://qmt-mcp/kline-chart-v1.html` resource and model/App visibility.
- `resources/read` returns `text/html;profile=mcp-app` with one self-contained
  document below the one MiB contract limit.
- Apps calls return concise text plus complete `structuredContent`; raw
  `qmt_xtdata_bars` rows remain behaviorally unchanged.
- Market OAuth scopes expose the chart; the core startup profile does not create
  or advertise the Apps extension.

## Visual evidence

See [`design-qa.md`](../../design-qa.md), which records the selected reference,
full and focused comparisons, interaction/state coverage, responsive checks,
and `final result: passed`.
