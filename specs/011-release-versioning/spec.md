# Feature Specification: Release & Versioning

**Status**: Draft (P2 — sustainable maintenance)
**Depends on**: 008 (CI), 007 (qmtctl, optional), 001 (image build)

## Summary

Make releases repeatable and traceable: a SemVer policy, a `CHANGELOG.md`, a
`VERSION` source of truth, and a tag-triggered pipeline that publishes the base
image to GHCR and (when 007 exists) cross-compiled `qmtctl` binaries to a GitHub
Release. Also closes the constitution-III deferral from 008 by declaring the
in-image Python deps for a generated lockfile.

## User Scenarios

### US1 — Cut a release (P2)
**Acceptance**: Bumping `VERSION`, updating `CHANGELOG.md`, and pushing a `vX.Y.Z`
tag triggers a workflow that builds + pushes `ghcr.io/<owner>/qmt-mcp`
tagged with the version and `latest`, and creates a GitHub Release.

### US2 — Pull a pinned image (P2)
**Acceptance**: A user can `docker pull ghcr.io/<owner>/qmt-mcp:X.Y.Z`
and get a reproducible base image.

### US3 — Reproducible Python deps (P2 / constitution III)
**Acceptance**: The in-image MCP deps are declared in `requirements.in`; a locked
`requirements.txt` is generated from the actual Wine build (`pip freeze`) and used
by the Dockerfile, replacing the unpinned `pip install fastmcp uvicorn ...`.

## Functional Requirements

- **FR-001**: SemVer policy documented; breaking changes to the broker-pack
  contract or exposed tool surface require a major/minor bump + migration note
  (mirrors the constitution's quality gates).
- **FR-002**: `CHANGELOG.md` in Keep-a-Changelog format with an `Unreleased`
  section seeded from existing history (001–010).
- **FR-003**: `VERSION` file as the single version source of truth.
- **FR-004**: `.github/workflows/release.yml` — on `v*` tag: build the amd64 base
  image and push to GHCR (`version` + `latest`); create a GitHub Release. Uses
  `GITHUB_TOKEN`/`packages: write`; needs no extra secrets.
- **FR-005**: Conditional `qmtctl` release — when the Go module exists, cross-build
  linux/macos/windows (amd64+arm64) and attach archives to the Release; skipped
  cleanly otherwise.
- **FR-006**: `requirements.in` declaring the MCP deps; documented lockfile-gen +
  Dockerfile wiring (the actual pin verification happens on an amd64 build).
- **FR-007**: Release notes/changelog never contain secrets.

## Success Criteria

- **SC-001**: `release.yml` is valid YAML and its job graph is coherent (image job
  always; cli job conditional).
- **SC-002**: `VERSION` parses as SemVer; `CHANGELOG.md` has the required sections.
- **SC-003**: `requirements.in` lists the four runtime deps; docs describe how to
  produce the locked `requirements.txt` from the Wine build.

## Out of Scope / Deferred

- Actually executing a release here (needs GitHub + an amd64 builder).
- Multi-arch image builds (the appliance is amd64-only by design).
- Signing/SBOM (future hardening).

## Assumptions / Dependencies

- GHCR is the registry; the publishing identity is the repo's `GITHUB_TOKEN`.
- The amd64 image build (001) is the artifact; CI here only orchestrates it.
