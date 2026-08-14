# Research: MCP App Story Prototype

## Decision: simulate a host conversation, not a page gallery

An MCP App is meaningful because it is returned by an agent tool call inside a
conversation. Isolated UI screenshots hide the user request, resolution steps,
tool choice, fallback behavior, and assistant conclusion. Each scene therefore
models a complete transcript with embedded interactive output.

## Decision: reuse the production frontend toolchain

The existing K-line workspace already pins the chart engine, icon library,
TypeScript, Vite, and single-file bundler. A second entry point avoids another
dependency tree and ensures prototype visuals stay compatible with production
App implementation.

## Decision: one typed fixture contract

Every scene declares navigation metadata, bilingual transcript copy, tool
activity, capability state, schema label, presentation, and renderer kind.
Renderers own only the scene-specific result body. This keeps future stories
additive.

## Decision: not every scene is an App

Simple explanations remain normal Agent messages, and small disambiguation
choices use a host-native confirmation result. A framed App is reserved for
visual exploration, multi-item comparison, portfolio risk, and guarded action
confirmation. The fixture's `presentation` field makes this product decision
explicit rather than deriving it from the renderer.

## Decision: natural document height

The prototype is a review document, not a production iframe. Scenes grow with
their content and use document scrolling so future long forms and analysis
surfaces are not clipped by a screenshot-oriented fixed height. Desktop and
mobile preview widths remain selectable.

## Decision: brand-neutral host chrome

The conversation should feel familiar to Codex or Claude users but must not
copy proprietary logos, names, or exact product chrome. It uses common chat,
tool-disclosure, composer, and embedded-attachment patterns.

## Decision: no production surface

The story file lives under `docs/prototypes` and is not registered by the MCP
server or included as an App resource. It is a design/review artifact only.
