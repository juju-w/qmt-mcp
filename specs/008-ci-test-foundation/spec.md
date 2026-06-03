# Feature Specification: CI & Test Foundation

**Status**: Draft (P0 — open-source launch gate)
**Depends on**: 002 (MCP core), 003/006 (xtdata + search modules under test)

## Summary

Give the repository an automated quality gate so external contributions and the
maintainer can land changes safely before the project goes public. Today there is
no CI, and verification is manual "live" runs that need a Wine appliance + a real
broker pack. This feature adds a **dependency-light, host-runnable test suite**
(no Wine, no `xtquant`, no broker pack) plus a **GitHub Actions pipeline** that
lints, runs the suite, scans for secrets, and compiles the Go CLI when present.

The key enabler: the MCP core's pure-logic modules (`config`, `errors`, `audit`,
`health`, `workers`, `registry`, xtdata `validation`/`serializers`) import only
the standard library. Only `app.py` and `xtdata/tools.py` import `fastmcp`, and
only `tools.py` touches `xtquant` (lazily). So the bulk of the logic is testable
on any plain Python 3.12 with zero third-party installs.

## User Scenarios

### US1 — Contributor opens a PR (P0)
**Acceptance**:
1. Given a pushed branch / opened PR, when CI runs, then lint + unit tests +
   secret scan execute and report pass/fail without needing Wine or a broker pack.
2. Given a lint or test failure, then the PR check is red with actionable output.

### US2 — Maintainer runs the suite locally (P0)
**Acceptance**:
1. Given a clean checkout and `pytest` available, when the maintainer runs the
   test command, then the unit suite passes with no third-party install beyond
   `pytest`/`ruff` (no `fastmcp`, no `xtquant`).
2. Given the Go CLI (007) exists, when its build job runs, then `go build`/`go vet`
   compile it; when it does not yet exist, the job is skipped cleanly.

### US3 — Secrets never merge (P0)
**Acceptance**:
1. Given a commit that adds a token/credential-looking string, then the secret
   scan flags it and the check fails.
2. Given the existing `.gitignore` excludes `.env`/packs, then a normal run is clean.

## Functional Requirements

- **FR-001**: A `tests/` suite for `appliance/mcp` that runs on host Python 3.12
  with **no** `fastmcp`/`uvicorn`/`xtquant`/broker pack — only `pytest`.
- **FR-002**: `qmt_mcp_core/__init__.py` MUST NOT import `fastmcp` at package-import
  time (lazy re-exports), so pure modules import standalone. Public API
  (`create_app`, `main`, `ToolRegistry`) is preserved via lazy access.
- **FR-003**: Unit coverage for: config parsing/validation + security fail-closed;
  error envelopes; JSONL audit sink; health/capability documents; worker-pool
  capacity/timeout; registry no-write-tools guarantee; xtdata validation +
  serializers. (Readiness/connector from 005 join once implemented.)
- **FR-004**: An optional "integration" test tier that exercises app assembly + the
  ASGI auth/`/healthz` path by installing `fastmcp` and injecting a **fake
  `xtquant`** module — marked so it is skipped when `fastmcp` is absent.
- **FR-005**: `ruff` lint + format-check configured (pyproject) over `mcp/`.
- **FR-006**: A GitHub Actions workflow running: ruff, pytest (unit tier), secret
  scan (gitleaks), and a conditional Go build for `qmtctl` (007) when its module
  exists.
- **FR-007**: CI MUST NOT require secrets, a broker pack, or amd64/Wine for the
  lint+unit+secret jobs (they run on stock `ubuntu-latest`).
- **FR-008**: A short `tests/README` (or contributing note) documenting how to run
  the suite and what is intentionally out of host scope (Wine/live xtdata).

## Success Criteria

- **SC-001**: `ruff check` and `pytest` (unit tier) both pass on a clean checkout
  with only `pytest`+`ruff` installed.
- **SC-002**: The workflow file is valid and its non-Wine jobs are reproducible by
  running the same commands locally.
- **SC-003**: A planted fake secret is caught by the secret-scan config.
- **SC-004**: Removing/breaking a pure module's invariant makes a specific unit
  test fail (the suite has real assertions, not smoke-only).

## Out of Scope / Deferred

- Building the Wine/amd64 image in CI (heavy; deferred to 011 release pipeline as
  a manual/nightly job).
- Pinning the in-image pip deps — recorded here as a known gap (constitution III)
  but the actual Dockerfile pin + verification needs an amd64 build (011).
- Live xtdata/xttrader integration tests (need a broker pack; stay manual).

## Assumptions / Dependencies

- Host/CI Python is 3.12 (matches the in-Wine runtime major.minor).
- `gitleaks` runs via its GitHub Action in CI (not required locally).
- 007 (qmtctl Go module) may or may not exist yet; its CI job is conditional.
