# Research: Interactive K-Line MCP App

## Decision 1: Use the official MCP Apps extension contract

**Decision**: Bind the chart tool with `_meta.ui.resourceUri`, serve a `ui://`
resource as `text/html;profile=mcp-app`, and advertise
`io.modelcontextprotocol/ui` through the Python SDK `Apps` extension.

**Rationale**: This is the official interoperable Tool + UI Resource model.
Apps-capable hosts may preload/cache the template and render it in a sandbox;
other hosts continue using the normal tool result.

**Sources**:

- https://modelcontextprotocol.io/extensions/apps/overview
- https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx
- https://github.com/modelcontextprotocol/python-sdk/blob/v2.0.0/src/mcp/server/apps.py

## Decision 2: Keep a dedicated chart tool

**Decision**: Add `qmt_xtdata_kline_chart`; do not attach App metadata to
`qmt_xtdata_bars`.

**Rationale**: Raw bars supports many codes, arbitrary fields, and large ranges.
The App needs one code, bounded OHLCVA rows, a display name, and chart summary.
A dedicated description also helps weaker agents choose correctly while
preserving the 1.0 bars contract.

**Alternative rejected**: Bind the existing bars tool. This creates ambiguous
rendering for multi-code results and makes UI constraints part of an established
general-purpose API.

## Decision 3: Bundle the official client SDK and a chart engine

**Decision**: Use `@modelcontextprotocol/ext-apps` for the iframe protocol and
Lightweight Charts for candlestick/volume rendering. Bundle both into one HTML
with Vite and `vite-plugin-singlefile`.

**Rationale**: The Apps protocol includes initialization, host context, tool
results, and optional server calls; hand-rolling its `postMessage` JSON-RPC
would be brittle. A maintained financial chart engine provides correct axes,
crosshair, zoom, resize, and efficient canvas rendering.

**Source**:

- https://github.com/modelcontextprotocol/ext-apps/blob/main/docs/quickstart.md
- https://tradingview.github.io/lightweight-charts/

## Decision 4: Static, versioned, offline resource

**Decision**: Use `ui://qmt-mcp/kline-chart-v1.html`; inline scripts/styles and
request no resource/connect domains or device permissions.

**Rationale**: Hosts may safely cache a versioned immutable template. Release
packages stay deterministic and the App works on isolated NAS/Windows systems.
Changing the wire-facing view contract requires a new resource version.

## Decision 5: Text fallback is a summary, not a row dump

**Decision**: Put a concise human/model-readable summary in `content` and all
chart rows in `structuredContent`.

**Rationale**: The Apps specification requires meaningful non-UI behavior.
Repeating hundreds of rows into model context is expensive and obscures the
answer; structured content remains available to clients that need the data.

## Decision 6: Host-driven locale and theme with safe defaults

**Decision**: Prefer Apps host context, then browser locale/color preference;
support `zh-CN` and English. Use light by default to match the selected design
and a balanced charcoal dark theme when requested.

**Rationale**: The same HTML runs in many hosts and launch environments. The
view must not assume ChatGPT-only globals or one fixed background.
