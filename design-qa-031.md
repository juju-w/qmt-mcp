# Design QA: MCP App Story Prototype

## Inputs

- Accepted concept:
  `~/.codex/generated_images/019e8947-cd73-7760-83d6-5fe085d9d01a/exec-eaba404d-4443-4c1b-b479-88838bb554f9.png`
  (`1505x1045`).
- Native-size implementation capture: temporary Playwright/Chrome capture at
  `1505x1045`, removed after `view_image` inspection.
- Tracked README capture: `docs/screenshots/mcp-app-storyboard.png`
  (`1536x1048`).
- Side-by-side evidence:
  `launcher/artifacts/design-qa/mcp-story-reference-implementation.png`.

## Fidelity Ledger

| Comparison point | Concept evidence | Render evidence | Resolution |
|---|---|---|---|
| Host skeleton | Left rail, compact host toolbar, transcript, composer, reviewer footer | Same regions and order at native height | Matched |
| Conversation context | User request, Agent lead, two tool rows, embedded chart, final answer | Same complete path; App is not a standalone dashboard | Matched |
| App anatomy | Quote header, period control, OHLC strip, K-line, volume, source footer | Same hierarchy with real Lightweight Charts canvas | Matched |
| Typography and density | Compact utility typography and tabular market values | Segoe/PingFang fallbacks, stable rows, no viewport-scaled type | Matched |
| Palette | True white/cool gray, green actions, red-up/green-down market colors | Same flat palette in light and dark themes; no gradients | Matched |
| Navigation model | Seven numbered story scenes | Only the review-ready K-line scene is visible | Intentional user-approved improvement; unfinished scenes are hidden |
| Height model | Single-screen concept | Long scenes grow and use document scrolling; composer remains reachable | Intentional user-approved improvement |
| Simple scenes | Concept framed every selected output | Demand is pure transcript; search is a compact disambiguation confirmation | Intentional user-approved improvement |

## Copy And Interaction

- The K-line first viewport preserves the concept's title, request, Agent lead,
  real tool names, instrument, quote, period labels, source, conclusion, composer,
  fixture mode, output format, schema, and response time.
- Added visible group labels (`Agent 对话`, `MCP App 页面`, `系统状态`) are from
  the user's later direction. No other unapproved above-the-fold copy remains.
- Exercised tool disclosure, K-line period switching, theme, locale, preview
  mode, and composer on the public scene.
- Confirmed that all six draft-scene deep links resolve to K-line and cannot
  expose their unfinished surfaces.

## Responsive And Runtime QA

- Viewports `1536x1048`, `1024x900`, `768x900`, and `390x844` were inspected.
- The post-hide pass repeated the accepted concept's native `1505x1045`
  viewport; document width matched the viewport and the final 9 vertical pixels
  remained available through normal page scrolling.
- At every measured width, document `scrollWidth == clientWidth`; longer scenes
  extend vertically and remain reachable by scrolling.
- Mobile navigation scrolls the selected scene into view without widening the
  document.
- The final packaged HTML made one document request and zero subresource or
  external requests. Browser console reported zero errors and warnings.
- K-line rendering produced 11 chart canvases; sampled chart pixels included
  1,144 non-background samples, confirming a nonblank render.

## Material Fixes

1. Reduced the chart height so the complete Agent answer remains visible at the
   concept viewport.
2. Replaced the seven undifferentiated pages with Agent/App/system groups.
3. Removed the unnecessary demand surface and replaced the search table with a
   compact, expandable confirmation result.
4. Removed fixed transcript height and repaired mobile grid min-width overflow.
5. Added active-scene auto-scroll for narrow horizontal navigation.
6. Hid all six non-K-line drafts after product review found their current
   presentation too close to formatted Markdown; retained their typed fixtures
   and renderers for a later redesign.

No blocking fidelity, responsiveness, interaction, accessibility, or asset
issues remain. The intentional differences above implement explicit user
feedback rather than unresolved drift.

final result: passed
