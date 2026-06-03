# Feature Specification: Open-Source Readiness

**Status**: Draft (P0 — open-source launch gate)
**Depends on**: none (repo hygiene); complements 008 (CI secret scan)

## Summary

Put the legal, security-disclosure, and contributor scaffolding in place so the
repository can be made public responsibly. Today the repo has no top-level
`LICENSE`, no `SECURITY.md`, and no `CONTRIBUTING.md`. Because this project is a
**trading appliance that touches broker accounts**, a responsible-disclosure
channel is not optional. Licensing must also be coherent with the already-MIT
vendored MCP code and the MIT base image.

## User Scenarios

### US1 — A user evaluates the license (P0)
**Acceptance**: A top-level `LICENSE` (MIT) exists; README's 许可 section links to
it; it is consistent with `mcp/vendor/LICENSE` and `mcp/NOTICE`.

### US2 — A researcher finds a vulnerability (P0)
**Acceptance**: `SECURITY.md` gives a private reporting channel, expected response
window, supported scope, and explicit "do not test against live broker accounts /
production trading" guidance.

### US3 — A contributor opens their first PR (P0)
**Acceptance**: `CONTRIBUTING.md` explains the spec-driven flow (spec → plan →
tasks → implement), how to run the 008 test suite, branch/commit conventions, and
the desensitization rule (no broker packs, tokens, account ids, or terminals).

## Functional Requirements

- **FR-001**: Top-level `LICENSE` = MIT, copyright "QMT-MCP Appliance
  contributors", year 2026; no conflict with vendored MIT.
- **FR-002**: `SECURITY.md` — private contact, response SLA (best-effort window),
  in-scope/out-of-scope, "no testing against production broker/trading accounts",
  and a note that secrets live only in the operator's QMT session (constitution VI).
- **FR-003**: `CONTRIBUTING.md` — dev setup, run tests (link `mcp/tests/README.md`),
  spec-driven workflow, branch naming (`NNN-feature`), commit/PR expectations,
  and the desensitization checklist before pushing.
- **FR-004**: README 许可 section links the new `LICENSE`.
- **FR-005**: Nothing added re-introduces secrets; the 008 secret scan stays clean.
- **FR-006**: Licensing/attribution remains accurate — the repo's own MIT does not
  claim the vendored author's copyright; `NOTICE` continues to attribute upstream.

## Success Criteria

- **SC-001**: `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md` exist at repo root with
  the required content.
- **SC-002**: A self-check for secret-like patterns over the new files is clean.
- **SC-003**: README links resolve to the new `LICENSE`.

## Out of Scope / Deferred

- `CODE_OF_CONDUCT.md` (optional; can follow later).
- GitHub issue/PR templates (nice-to-have; defer).
- Choosing a non-MIT license (MIT is fixed by the existing components).

## Assumptions / Dependencies

- Contact for disclosure: the maintainer email already in repo metadata.
- 008 provides the secret-scan enforcement that FR-005 relies on.
