# Feature Specification: Interactive K-Line MCP App

**Feature Branch**: `codex/030-mcp-kline-app`

**Created**: 2026-08-14

**Status**: Approved

**Input**: Continue MCP Apps support after the 1.0 modern-only protocol release;
ship the first read-only interactive K-line experience.

**Depends on**: 003 (xtdata), 006 (instrument resolution), 020 (tool
contracts), 029 (MCP 2026-07-28 only).

## Summary

Add a dedicated single-instrument K-line tool and bind it to a self-contained
MCP Apps HTML resource. Apps-capable hosts render a responsive candlestick and
volume chart; every other host receives a concise text summary and the same
chart-ready structured data.

The selected visual target is ideation option 2: a light research canvas with a
slim instrument header, compact period/adjustment controls, a dominant K-line
plot, aligned volume, hover OHLC details, and a quiet source footer.

## User Scenarios & Testing

### User Story 1 - Ask AI to show one instrument's K-line (Priority: P1)

A user asks to view the recent K-line for an exact instrument or a name the
agent can first resolve. The agent selects the dedicated chart tool and the host
renders an interactive chart directly in the conversation.

**Independent Test**: Call `qmt_xtdata_kline_chart` with a fake xtdata backend,
read its `ui://` resource, and render the returned structured data in a test
host/browser.

**Acceptance Scenarios**:

1. **Given** a valid QMT code, **when** the tool is called, **then** it returns
   normalized OHLCVA rows, instrument metadata, range statistics, and a concise
   text summary.
2. **Given** an Apps-capable host, **when** it lists and calls the tool, **then**
   `_meta.ui.resourceUri` points to a readable
   `text/html;profile=mcp-app` resource.
3. **Given** a name rather than a code, **when** an agent reads the tool
   description, **then** it is instructed to resolve the instrument first and
   never guess a code.

---

### User Story 2 - Explore the chart without another prompt (Priority: P1)

A user hovers, changes the visible range, or switches the period/adjustment
control and can inspect prices and volume without parsing a large text table.

**Independent Test**: Load the selected-design fixture in a browser at desktop
and narrow widths; exercise crosshair, period, adjustment, zoom, and theme
changes.

**Acceptance Scenarios**:

1. **Given** loaded rows, **when** the pointer moves across candles, **then** the
   date, open, high, low, close, change, volume, and amount readout follows the
   selected candle without moving surrounding layout.
2. **Given** a supported period or adjustment change, **when** the user selects
   it, **then** the App calls the same server tool through the host and replaces
   the chart only after a successful result.
3. **Given** a host theme or locale change, **when** the App receives updated
   host context, **then** it switches between light/dark tokens and Chinese/
   English labels without reload.
4. **Given** a narrow container, **when** the App reflows, **then** labels,
   controls, chart axes, and status text remain readable and do not overlap.

---

### User Story 3 - Degrade gracefully in non-App hosts (Priority: P1)

A user on a client without MCP Apps support can still use the K-line tool as a
normal read-only data tool.

**Independent Test**: Call the tool with no Apps capability and verify its text
content, structured output, annotations, and error behavior.

**Acceptance Scenarios**:

1. **Given** a host without Apps support, **when** the tool succeeds, **then** it
   receives a human-readable instrument/date/bar-count/price-change summary and
   structured rows.
2. **Given** missing history or an xtdata failure, **when** the tool returns,
   **then** both App and text hosts receive the established structured error
   envelope with no blank iframe.
3. **Given** the `market`, `readonly`, or `full` profile, **when** tools are
   listed, **then** the chart tool follows the same visibility and OAuth market
   scope rules as other xtdata tools.

### Edge Cases

- A period is valid in xtdata but not meaningful for candlestick rendering.
- A row is missing OHLC, contains zero/negative prices, or has duplicate times.
- xtdata returns timestamps in date, datetime, epoch-second, or epoch-millisecond
  form.
- Only one valid bar is available, so change statistics have no previous close.
- The host sends the result before/after the iframe handshake or updates its
  theme/locale later.
- The host does not support UI-to-server tool calls; initial rendering still
  works and unsupported controls stay disabled.
- The packaged HTML is missing or stale relative to frontend source.

## Requirements

### Functional Requirements

- **FR-001**: The server MUST expose `qmt_xtdata_kline_chart` only when xtdata is
  enabled and the active tool profile permits xtdata read tools.
- **FR-002**: The tool MUST accept one exact QMT code, a supported K-line period,
  bounded date/count arguments, and a supported dividend-adjustment mode.
- **FR-003**: The tool description/docstring MUST tell an AI when to use this
  chart tool, when to use `qmt_xtdata_bars`, and when to resolve a name first.
- **FR-004**: The tool MUST reuse the existing validated xtdata/warehouse bars
  path rather than implement a second data reader.
- **FR-005**: The tool MUST return a concise text fallback plus structured
  instrument, range, summary, and normalized OHLCVA row data.
- **FR-006**: The tool MUST be read-only, idempotent, audited, market-scoped,
  worker-backed, and protected by the existing timeout/error envelope.
- **FR-007**: The tool MUST advertise `_meta.ui.resourceUri` for a versioned
  `ui://` resource and default visibility to both model and App.
- **FR-008**: The server MUST advertise the official
  `io.modelcontextprotocol/ui` extension when the App tool is present.
- **FR-009**: The UI resource MUST use
  `text/html;profile=mcp-app`, be self-contained, request no device permissions,
  and require no external network origin.
- **FR-010**: The App MUST use the official `@modelcontextprotocol/ext-apps`
  client SDK for host communication and a maintained chart library for K-line
  rendering.
- **FR-011**: The App MUST render candlesticks, volume, date/price axes, MA5/
  MA10/MA20, hover/crosshair values, source, range, bar count, and data status.
- **FR-012**: Period and adjustment controls MUST call the dedicated tool via
  the host when supported and preserve the previous chart on request failure.
- **FR-013**: The App MUST support light/dark host themes, Simplified Chinese
  and English labels, loading/empty/error states, keyboard focus, and responsive
  layouts down to 360 CSS pixels.
- **FR-014**: Chinese-market color semantics MUST be red-up and green-down, with
  text/icons in addition to color for statuses where color alone is ambiguous.
- **FR-015**: The frontend MUST build to one tracked HTML artifact; Linux and
  Windows runtime packages MUST not require Node or a CDN.
- **FR-016**: CI MUST prove the frontend build is reproducible and cover the
  server metadata, resource read, tool success/error, profile, OAuth, and native
  Windows package inclusion paths.
- **FR-017**: Existing `qmt_xtdata_bars` behavior and schema MUST remain
  backward compatible.

## Key Entities

- **KLineQuery**: Exact code, period, optional range/count, dividend adjustment.
- **KLineBar**: Normalized timestamp plus OHLC, volume, and amount values.
- **KLineSummary**: Latest/previous close, absolute and percentage change,
  visible-range high/low, bar count, and source.
- **KLineAppResource**: Versioned, cacheable, self-contained HTML template.

## Success Criteria

- **SC-001**: An Apps-capable protocol fixture discovers one valid UI-bound tool
  and reads its referenced resource with the required MIME type.
- **SC-002**: 100% of tested non-App calls receive meaningful text and matching
  structured output; no successful call returns only UI metadata.
- **SC-003**: Browser tests render nonblank chart/volume pixels and pass primary
  interactions at 1440x1024, 768x900, and 390x844 without overlap.
- **SC-004**: Frontend tests cover locale/theme changes, valid/empty/error
  results, and period/adjustment refresh behavior.
- **SC-005**: Python unit/integration, frontend, Go, launcher, packaging, and
  policy checks remain green.

## Out of Scope

- Multi-instrument comparison, indicators beyond moving averages, drawing
  tools, alerts, exports, streaming subscriptions, and order placement.
- A generic dashboard framework or a second web service.
- Shipping xtquant, broker binaries, Node, or browser assets in release packs.
- Claiming every MCP host supports Apps; the text fallback remains first-class.

## Assumptions

- MCP core remains `2026-07-28`; MCP Apps uses extension revision `2026-01-26`.
- Official Python MCP SDK `2.0.0` remains the server integration baseline.
- Host implementations may differ in optional tool-call, theme, locale, and
  fullscreen capabilities; initial result rendering is the portable baseline.
