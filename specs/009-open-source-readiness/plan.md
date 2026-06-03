# Implementation Plan: Open-Source Readiness

**Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

## Summary

Add root `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`; link the license from
README. Pure documentation/legal scaffolding — no code paths change.

## Technical Context

**Language/Version**: Markdown + a plain-text MIT license. No build impact.
**Testing**: file-existence + a secret-pattern self-check + README link resolution.
**Constraints**: keep the 008 secret scan clean; do not misattribute the vendored
author's copyright (constitution VI on accurate attribution / no secrets).

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| VI. Security by Default | Adds a disclosure channel; reaffirms secrets-never-committed | PASS |
| VII. Spec-Driven | Scoped to repo hygiene; no behavior change | PASS |
| (others) | Documentation-only | N/A |

## Project Structure

```text
LICENSE             # NEW (MIT)
SECURITY.md         # NEW
CONTRIBUTING.md     # NEW
README.md           # MODIFY: 许可 section links LICENSE
```

**Structure Decision**: Root-level community-health files (GitHub conventions) so
they surface in the repo UI. `NOTICE`/`vendor/LICENSE` stay where they are.

## Complexity Tracking

> Not required.
