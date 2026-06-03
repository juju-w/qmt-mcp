# Implementation Plan: Release & Versioning

**Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

## Summary

Add versioning metadata + a tag-triggered release workflow. Image build is
amd64-only (reused from 001), orchestrated by GitHub Actions on `v*` tags. Declare
MCP deps for a generated lockfile to close the 008 pinning deferral.

## Technical Context

**Language/Version**: YAML workflow, Markdown, a plain `VERSION` file, a
`requirements.in`. Go cross-build only when 007 exists.
**Testing**: YAML parse + SemVer/format checks here; the actual image push and
binary build require GitHub + amd64 (out of local scope).
**Constraints**: no secrets in notes; reproducible/pinned (III); amd64-only image.

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| III. Reproducible / Native / Pinned | Versioned images + declared deps/lockfile path | PASS |
| VI. Security by Default | Release notes secret-free; uses scoped `GITHUB_TOKEN` | PASS |
| VII. Spec-Driven | Versioning gates mirror the constitution's breaking-change rule | PASS |

## Project Structure

```text
VERSION                          # NEW: single version source of truth
CHANGELOG.md                     # NEW: Keep-a-Changelog
.github/workflows/release.yml    # NEW: tag -> GHCR image + Release (+ optional CLI)
qmt-wine-rdp/mcp/requirements.in # NEW: declared MCP runtime deps (lock generated on build)
```

**Structure Decision**: Root `VERSION`/`CHANGELOG` (discoverable); release workflow
separate from `ci.yml` so PR CI stays fast and release runs only on tags.

## Complexity Tracking

> Not required.
