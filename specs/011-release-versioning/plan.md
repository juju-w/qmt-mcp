# Implementation Plan: Release & Versioning

**Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

## Summary

Upgrade versioning from manual tags to CI-gated automatic releases. CI validates
Conventional Commits; successful `main` CI computes SemVer, updates version and
changelog metadata, pushes a release commit/tag, then publishes the amd64 image
and six qmtctl packages in one retryable workflow.

## Technical Context

**Language/Version**: GitHub Actions YAML, Python 3.12 release-policy helper,
Markdown, plain `VERSION`, Go 1.22 cross-build.
**Testing**: release-policy unit tests, YAML/action lint, existing Python/Go CI,
local six-target cross-build, and the real GitHub release run after merge.
**Constraints**: no secrets in notes; reproducible/pinned (III); amd64-only image.

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| III. Reproducible / Native / Pinned | Versioned images + declared deps; amd64 lock generation remains | PARTIAL |
| VI. Security by Default | Release notes secret-free; uses scoped `GITHUB_TOKEN` | PASS |
| VII. Spec-Driven | Updated 011 spec/plan/tasks describe automatic delivery | PASS |

## Project Structure

```text
VERSION                          # NEW: single version source of truth
CHANGELOG.md                     # NEW: Keep-a-Changelog
.github/workflows/ci.yml         # PR/main checks + commit policy
.github/workflows/release.yml    # successful main CI -> version/tag/artifacts/Release
.github/scripts/release_policy.py
appliance/mcp/requirements.in # NEW: declared MCP runtime deps (lock generated on build)
docs/RELEASE.md               # cache, China mirror, retry, and permissions
```

**Structure Decision**: Root `VERSION`/`CHANGELOG` remain authoritative. CI stays
fast and secret-free; release runs only after successful main CI. Release policy
is testable Python instead of duplicated, opaque shell regexes.

The image is built once to GHCR. A `mode=max` registry cache preserves
intermediate Wine/Python layers beyond GitHub cache eviction, while the old GHA
cache remains an import-only migration fallback. An optional ACR/TCR/SWR target
is populated by copying the built digest with `buildx imagetools`; it never
executes the Dockerfile again.

## Complexity Tracking

> Not required.
