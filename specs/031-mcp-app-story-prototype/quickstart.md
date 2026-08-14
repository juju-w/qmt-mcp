# Quickstart: MCP App Story Prototype

```bash
cd appliance/mcp/apps/kline
npm ci
npm run dev:story
```

Open:

```text
http://127.0.0.1:4173/qmt-mcp-app-story.html?scene=kline
```

Build the tracked single-file artifact:

```bash
npm run typecheck
npm test
npm run build:story
```

Then open `docs/prototypes/qmt-mcp-app-story.html` directly or serve the
directory with any static HTTP server. No QMT or MCP service is required.

The left navigation distinguishes host-native Agent scenes from real MCP App
pages. Longer pages scroll naturally; a scene does not need to fit a fixed
prototype height.
