# Design QA: Interactive K-Line MCP App

## Inputs

- Reference: `~/.codex/generated_images/019e8947-cd73-7760-83d6-5fe085d9d01a/exec-3545b8d8-ce5e-48ef-b8b6-12b497ecbd5c.png`
  (`1487x1058`), user-selected visual option 2.
- Implementation: `docs/screenshots/kline-mcp-app.png` (`1440x900`), captured
  from a `1440x1024` viewport with the light Chinese success fixture.
- Full side-by-side evidence:
  `launcher/artifacts/design-qa/kline-reference-implementation.png`.
- Focused header/toolbar evidence:
  `launcher/artifacts/design-qa/kline-header-comparison.png`.
- Responsive evidence: `kline-tablet-dark-en.png`, `kline-mobile-zh.png`,
  `kline-mobile-empty.png`, and `kline-mobile-error.png` in the same artifact
  directory.

## Comparison

- Layout and spacing: both versions use a thin identity/quote header, compact
  period and adjustment controls, a single dominant chart, a separate volume
  pane, and a restrained footer. The implementation is intentionally denser to
  fit an embedded conversation surface, while preserving the target hierarchy.
- Typography: Segoe/PingFang-compatible fallbacks, tabular quote figures, and
  compact labels remain legible at desktop, tablet, and mobile sizes. Text does
  not overlap or resize the fixed chart controls.
- Color and surfaces: flat white/dark surfaces, light dividers, green brand
  accents, Chinese-market red-up/green-down states, and blue/orange/purple
  moving averages match the selected direction. No decorative gradients,
  shadows, or nested cards were introduced.
- Icons: all visible controls use Lucide icons with consistent stroke and size.
  Fullscreen changes to the matching exit icon; error retry uses RefreshCw.
- Content: instrument, OHLC, change, volume, amount, source, range, bar count,
  and status are coherent and use realistic fixture data. English and Chinese
  labels were both inspected.
- Imagery: the product is the chart itself; candlesticks, moving averages, and
  volume are rendered by Lightweight Charts rather than placeholder artwork.
  Pixel sampling found nontransparent and colored pixels in both chart panes.

## States And Accessibility

- Exercised daily to weekly switching, forward to backward adjustment,
  fullscreen entry/exit, chart hover updates, zoom-capable canvas, and error
  retry back to success.
- Inspected success, empty, initial error, recovery, light Chinese, and dark
  English states.
- Semantic buttons, pressed states, select labels, alert roles, title tooltips,
  keyboard focus outlines, and reduced-motion handling are present.
- Viewports `1440x1024`, `768x900`, and `390x844` reported document
  `scrollWidth == clientWidth`; no overlapping or unusable controls were found.
- Browser console reported zero errors and warnings in the final source and
  packaged-resource passes.

## Iterations

1. Increased chart height and added visible MA5/MA10/MA20 values after the first
   desktop comparison showed too much unused space.
2. Fixed the final fixture bar to a positive `136.42` quote so semantic color
   and state match the selected reference.
3. Added a real retry command to the error state and verified it restores the
   success chart.
4. Rejected invalid timestamps and OHLC envelopes in both Python and TypeScript
   normalization before rendering.
5. Bundled the Apps bridge, chart engine, styles, and icons into one HTML file;
   a standalone server pass made one static request and no external requests.

## Accepted Deltas

- The reference shows additional volume moving-average lines. The implemented
  v1 scope keeps MA5/10/20 on price and raw volume bars, which avoids adding an
  undocumented indicator and remains faithful to the selected information
  hierarchy.
- The reference is a taller presentation mock. The implementation uses bounded
  desktop/tablet/mobile heights suitable for MCP Host iframes and allocates the
  saved space to a larger usable plotting area.

No blocking fidelity, responsiveness, interaction, accessibility, or asset
issues remain.

final result: passed
