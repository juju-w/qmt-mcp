# Verification: MCP App Story Prototype

## Frontend And Artifact

| Surface | Result |
|---|---|
| TypeScript | `npm run typecheck` passed |
| Vitest | 7 tests passed across 2 files |
| Single-file build | 242.11 KB raw / 77.44 KB gzip; deterministic SHA-256 `306c1d86032b53b04dd87a084b286fa36f7ef99d37f0acd7f6665d85a03a3849` |
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

- Only the review-ready K-line scene is visible. The other six scenes remain
  typed draft fixtures but are hidden from navigation and deep links.
- Empty Agent conversation and system-status groups are omitted from the rail.
- Scene, locale, theme, and desktop/mobile preview are reflected in the URL.
- Long scenes grow naturally and use document scrolling instead of a fixed
  screenshot height.

## Browser Evidence

- Exercised the public K-line scene and period controls with Playwright using
  the installed Chrome channel because the bundled Chromium cache was
  unavailable.
- Verified every non-K-line deep link resolves to the public K-line scene.
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
