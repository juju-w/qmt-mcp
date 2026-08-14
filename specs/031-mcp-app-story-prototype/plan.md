# Implementation Plan: MCP App Story Prototype

## Technical Context

- Reuse `appliance/mcp/apps/kline` with TypeScript 7, Vite 8,
  `vite-plugin-singlefile`, Lucide, and Lightweight Charts.
- Add a separate story entry point and Vite configuration; do not duplicate the
  package lock or introduce React into the existing vanilla TypeScript surface.
- Generate `docs/prototypes/qmt-mcp-app-story.html` deterministically.
- Keep scene fixtures, shell rendering, scene rendering, and format helpers in
  separate modules.

## Visual Target

The accepted direction is the generated host-conversation concept at
`~/.codex/generated_images/019e8947-cd73-7760-83d6-5fe085d9d01a/exec-eaba404d-4443-4c1b-b479-88838bb554f9.png`.
It preserves the QMT K-line design system while placing each App in a
brand-neutral Codex/Claude-style transcript.

## Architecture

```text
qmt-mcp-app-story.html
  -> src/story/main.ts
     -> scenes.ts       typed bilingual fixture/story data
     -> model.ts        deep-link resolution and ranking helpers
     -> renderers.ts    App and host-native result surfaces
     -> chart.ts        Lightweight Charts K-line rendering
     -> style.css       responsive design system

vite.story.config.ts
  -> docs/prototypes/qmt-mcp-app-story.html
```

## Constitution Check

- Broker-neutral: documentation fixture only; no broker data or binaries.
- Read-only default: no API calls; trade scene is visibly permission-gated and
  only previews a plan.
- Reproducible: pinned existing workspace and deterministic tracked artifact.
- Contract-first: typed scene fixture contract is documented.
- Security: fixtures contain no secrets, real accounts, endpoints, or hosts.
- Spec-driven: this plan follows the approved feature specification.

No constitution exception is required.

## Verification Strategy

- TypeScript typecheck and Vitest fixture/helper tests.
- Rebuild and `git diff --exit-code` artifact drift check.
- Static-server request inspection proves no runtime dependencies.
- Browser interaction checks for scene selection, tool disclosure, theme,
  language, viewport mode, K-line controls, trade preview, and recovery.
- Screenshots and canvas-pixel checks at desktop, tablet, and mobile widths.
- Side-by-side visual review against the accepted concept.
