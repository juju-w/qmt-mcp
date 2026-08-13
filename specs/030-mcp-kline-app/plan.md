# Implementation Plan: Interactive K-Line MCP App

**Branch**: `codex/030-mcp-kline-app` | **Date**: 2026-08-14 | **Spec**:
`specs/030-mcp-kline-app/spec.md`

## Summary

Add the first QMT-MCP App as a dedicated xtdata chart tool. Refactor the current
bars reader into one shared validated function, register an official Python SDK
`Apps` extension before server construction, and serve a single-file TypeScript
view built with the official Apps client and Lightweight Charts.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 7; Node 24 at build/test time; Go
1.25 and .NET 10 unchanged

**Primary Dependencies**: MCP Python SDK 2.0.0; `@modelcontextprotocol/ext-apps`
1.7.5; `lightweight-charts` 5.2.1; Vite 8.2.1;
`vite-plugin-singlefile` 2.3.3

**Storage**: Existing optional PostgreSQL bars warehouse; no schema change

**Testing**: pytest unit/integration; Vitest/DOM tests; Playwright visual and
interaction checks; existing Go/.NET/policy suites

**Target Platform**: MCP App iframe in compatible hosts; same Linux/Wine and
Windows x64 Python server packages; plain-text fallback everywhere else

**Performance Goals**: one bounded chart call (default 120, max 1000 bars),
single HTML resource below 1 MiB, local hover/zoom under one animation frame

**Constraints**: no external runtime network, no Node in release packages, no
broker or trading permission in tests, no change to raw bars contract

**Scale/Scope**: one chart tool, one static resource, one responsive screen

## Constitution Check

- **I Broker-agnostic**: Pass. Uses normalized xtdata calls and no broker paths.
- **II Read-only default**: Pass. Chart calls only validated market-data reads.
- **III Reproducible pinned builds**: Pass. Exact npm versions and lockfile;
  generated HTML is checked for drift in CI.
- **IV Contract-first MCP**: Pass. Tool/resource/output contracts precede code.
- **V Observable/auditable**: Pass. The App tool uses the shared registry audit
  wrapper and exposes source/status in both outputs.
- **VI Security by default**: Pass. Sandboxed self-contained resource, no CSP
  origins or permissions, existing auth/profile/OAuth gates retained.
- **VII Spec-driven delivery**: Pass. Work is isolated to feature 030.

Post-design re-check: no constitution exception or complexity waiver is needed.

## Design

### Server composition

Create the registry and optional warehouse before constructing `MCPServer`.
When xtdata and its profile are enabled, create `mcp.server.apps.Apps`, load the
tracked HTML resource, register the audited chart callable on that extension,
and append it to the server's extension list. Normal tools continue registering
directly after server construction.

Extend the registry adapter narrowly so an audited tool can be registered via
`Apps.tool(resource_uri=...)` and can provide a short text serializer while
retaining the common structured output schema, annotations, visibility, OAuth,
and error behavior.

### Shared market-data path

Extract the body of `qmt_xtdata_bars` into a module-level validated reader used
by both raw bars and chart tools. The chart tool fixes fields to OHLCVA, limits
one code, obtains the display name best-effort, normalizes usable rows, and
computes deterministic summary values.

### App frontend

Use a small TypeScript/Vite workspace under `appliance/mcp/apps/kline`. Bundle
the official Apps SDK, Lightweight Charts, CSS, and application code into
`qmt_mcp_apps/resources/kline-chart-v1.html`. The view handles initial tool
input/result before connecting, optional server-tool refreshes, host context
changes, and static fixture mode for browser QA.

Recreate selected visual option 2: a light research canvas with balanced dark
tokens, no outer card, stable header/control/status rows, dominant K-line plot,
aligned volume, and responsive wrapping. Use the host locale/theme when
provided and browser preferences otherwise.

### Verification

- Python unit tests for row normalization, summary/text, registry App metadata,
  and raw bars parity.
- Protocol integration tests for extension discovery, tool metadata,
  `resources/read`, Apps/non-Apps calls, profile and OAuth filtering.
- Frontend build and unit tests for parsing, localization, theme, and refresh.
- Playwright captures against static fixture mode at desktop/tablet/mobile,
  including canvas-pixel and overlap checks plus crosshair/control interaction.
- Windows packaging test asserts the generated App resource is included.

## Project Structure

```text
specs/030-mcp-kline-app/
├── spec.md
├── plan.md
├── research.md
├── tasks.md
├── quickstart.md
└── contracts/kline-app.md

appliance/mcp/apps/kline/
├── package.json
├── package-lock.json
├── index.html
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── main.ts
    ├── style.css
    └── *.test.ts

appliance/mcp/qmt_mcp_apps/
├── __init__.py
├── kline.py
└── resources/kline-chart-v1.html

appliance/mcp/qmt_mcp_core/
├── app.py
├── registry.py
└── tool_contracts.py

appliance/mcp/qmt_mcp_xtdata/tools.py
appliance/mcp/tests/
.github/workflows/ci.yml
README.md
README.en.md
```

**Structure Decision**: Keep the browser source build-only and the generated
single HTML inside a `qmt_mcp_*` package so existing Docker and Windows copy
rules include the runtime artifact automatically.

## Complexity Tracking

No constitution violations. The dedicated tool avoids binding UI semantics to
the existing multi-code raw-bars contract.
