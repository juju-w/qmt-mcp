# Feature Specification: MCP App Story Prototype

**Feature Branch**: `codex/031-mcp-app-story-prototype`
**Created**: 2026-08-14
**Status**: Approved for implementation

## Goal

Provide one self-contained HTML prototype that reviewers can open without QMT,
an MCP Host, a backend, or a network connection. A scene rail on the left
selects a complete user journey; the right side shows how that journey appears
inside a brand-neutral Codex/Claude-style agent conversation, including user
messages, assistant narration, tool activity, embedded MCP App UI, and the final
assistant response.

## User Scenarios

### US1 - Review a complete agent story (P1)

A product or engineering reviewer selects any scene and sees the complete
conversation that motivates and contains the corresponding MCP App.

**Acceptance**:

1. The left rail exposes only the review-ready K-line scene. Draft scenes remain
   in source fixtures but are not user reachable, and empty groups are omitted.
2. Selecting a scene updates the title, user message, assistant narration, tool
   rows, embedded App, assistant conclusion, schema, and capability status.
3. The right side is recognizably a real AI chat surface, not a standalone
   dashboard or screenshot gallery.
4. Only the review-ready K-line scene uses a framed MCP App. Simpler steps
   remain normal conversation or inline results; unfinished App concepts stay
   hidden until they meet the same product-quality bar.

### US2 - Exercise the prototype (P1)

A reviewer can operate the visible scene controls and inspect realistic state
changes without making network calls.

**Acceptance**:

1. Tool rows expand and collapse.
2. K-line period controls have meaningful local behavior.
3. All non-K-line draft scenes cannot be opened from navigation or direct URL
   parameters.

### US3 - Review host and responsive variants (P2)

A reviewer can inspect Chinese/English, light/dark, and desktop/mobile preview
states from the same file.

**Acceptance**:

1. Theme and language controls update all prototype chrome and scene copy.
2. Desktop/mobile controls resize the simulated host canvas.
3. The document remains usable at 1440, 1024, 768, and 390 CSS-pixel widths.
4. Long scenes grow naturally and remain reachable through document scrolling;
   the prototype does not depend on a fixed preview height.

### US4 - Reuse the workflow for future Apps (P2)

Contributors can add a future App scene through typed fixture data and a focused
renderer without changing the prototype shell.

## Requirements

- **FR-001**: Deliver exactly one generated HTML artifact at
  `docs/prototypes/qmt-mcp-app-story.html`.
- **FR-002**: The artifact MUST inline JavaScript, CSS, icons, and chart code and
  MUST make no runtime network request.
- **FR-003**: The source MUST reuse the locked frontend workspace and its pinned
  dependencies.
- **FR-004**: Every scene MUST contain host conversation context; scenes MUST
  only introduce a framed App when a visual, comparative, risk, or confirmation
  surface materially improves the response.
- **FR-005**: Scene selection MUST be shareable through the URL query string.
- **FR-006**: Tool rows MUST show realistic tool names, arguments/results, and
  success/error states without exposing credentials or account identifiers.
- **FR-007**: Implemented capability and planned/permissioned capability MUST be
  visually and textually distinct.
- **FR-008**: The prototype MUST not call trading, market-data, MCP, or account
  APIs.
- **FR-009**: Visible UI controls MUST be keyboard reachable and have accessible
  labels and focus states.
- **FR-010**: CI MUST rebuild the artifact and fail on drift.
- **FR-011**: Scene fixtures MUST declare public or draft visibility. Navigation
  and URL resolution MUST exclude draft scenes without deleting their source.

## Non-Goals

- Registering another production MCP tool or `ui://` resource.
- Cloning proprietary Codex or Claude branding.
- Executing orders, reading a real account, or connecting to QMT.
- Replacing the production K-line App fixture and protocol tests.

## Success Criteria

- A new reviewer can understand the full QMT-MCP App story from the single file.
- The public K-line scene and its primary controls work without network access.
- The final build loads with one HTML request, zero external requests, and zero
  browser-console errors.
- Visual QA records no overlap or document-width overflow at the required
  viewports.
