# Quickstart: Interactive K-Line MCP App

## Build the single-file view

```bash
cd appliance/mcp/apps/kline
npm ci
npm run build
npm test
```

The build writes
`appliance/mcp/qmt_mcp_apps/resources/kline-chart-v1.html`. CI rebuilds it and
fails if the tracked artifact differs.

## Run Python tests

```bash
cd appliance/mcp
ruff check .
ruff format --check .
pytest -m 'not integration'
pytest -m integration
```

## Browser fixture

```bash
cd appliance/mcp/apps/kline
npm run dev -- --host 0.0.0.0 --port 4173 --strictPort
```

Open `http://localhost:4173/?fixture=success`. Also verify `fixture=empty` and
`fixture=error`, light/dark theme, Chinese/English locale, hover/crosshair,
period/adjustment controls, and widths 1440, 768, and 390.

## Protocol checks

With the modern request metadata and an xtdata-enabled test server:

1. `server/discover` advertises `io.modelcontextprotocol/ui`.
2. `tools/list` exposes `qmt_xtdata_kline_chart` with
   `_meta.ui.resourceUri=ui://qmt-mcp/kline-chart-v1.html`.
3. `resources/read` returns one text content item with MIME
   `text/html;profile=mcp-app`.
4. `tools/call` returns concise text plus matching structured chart data.
