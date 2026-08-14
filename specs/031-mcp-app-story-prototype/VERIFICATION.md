# Verification: MCP App Story Prototype

## Frontend And Artifact

| Surface | Result |
|---|---|
| TypeScript | `npm run typecheck` passed |
| Vitest | 7 tests passed across 2 files |
| Single-file build | 241.83 KB raw / 77.35 KB gzip |
| Runtime requests | one HTML request; zero subresource or external requests |
| Browser console | zero errors and warnings |
| Python | ruff passed; 243 unit tests passed, 1 PostgreSQL test skipped |
| MCP integration | 55 tests passed |
| Go qmtctl | test, vet, package build, and conformance build passed on Go 1.25 |
| Repository policy | 16 Python policy tests, actionlint, and `git diff --check` passed |

The tracked artifact is `docs/prototypes/qmt-mcp-app-story.html`. It contains
the story shell, fixtures, styles, Lucide icons, and Lightweight Charts runtime
and does not connect to QMT, MCP, account, or trading services.

## Product Contract

- Seven selectable scenes are grouped as Agent conversation, MCP App pages,
  and system status.
- Only K-line, ETF comparison, portfolio risk, and trade confirmation render a
  framed App. Demand stays in the transcript and search uses inline
  disambiguation confirmation.
- Scene, locale, theme, and desktop/mobile preview are reflected in the URL.
- Trading is visibly proposed and permission-gated; the preview creates no
  order and connects to no account.
- Long scenes grow naturally and use document scrolling instead of a fixed
  screenshot height.

## Browser Evidence

- Exercised all scene links and scene-specific controls with Playwright CLI.
- Checked Chinese/English, light/dark, tool disclosure, composer feedback, and
  recovery transitions.
- Verified `1536x1048`, `1024x900`, `768x900`, and `390x844`; measured no
  document-width overflow.
- Confirmed a nonblank chart through visual inspection and canvas pixel
sampling.

The local Mac does not have `dotnet` installed. Native launcher builds and the
Windows x64 package smoke remain covered by the required PR checks; this
documentation-only prototype does not alter launcher source or packaging.

See [`design-qa-031.md`](../../design-qa-031.md) for the native-size concept
comparison, fidelity ledger, accepted deltas, and `final result: passed`.
