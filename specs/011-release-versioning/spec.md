# Feature Specification: Release & Versioning

**Status**: Complete (P2 - sustainable maintenance)
**Depends on**: 008 (CI), 007 (qmtctl, optional), 001 (image build)

## Summary

Make releases automatic, repeatable, and traceable: Conventional Commits drive a
SemVer policy, `VERSION` and `CHANGELOG.md` are updated by CI, and a successful
`main` build publishes the base image to GHCR plus packaged `qmtctl` binaries to
one GitHub Release. Also closes the constitution-III deferral from 008 by
declaring the in-image Python deps for a generated lockfile.

## User Scenarios

### US1 - Publish after merging (P2)
**Acceptance**: After CI succeeds on `main`, commits since the last release are
classified using Conventional Commits, `VERSION` and `CHANGELOG.md` are updated
in `chore(release): vX.Y.Z [skip ci]`, and that commit is tagged automatically.

### US2 - Pull a pinned image (P2)
**Acceptance**: A user can `docker pull ghcr.io/<owner>/qmt-mcp:X.Y.Z`
and get a reproducible base image.

### US3 - Download a native CLI package (P2)
**Acceptance**: A GitHub Release contains qmtctl archives for Linux, macOS, and
Windows on amd64 and arm64 plus `SHA256SUMS`.

### US4 - Declared Python deps and lock path (P2 / constitution III)
**Acceptance**: The Dockerfile installs the in-image MCP deps from
`requirements.in`; generating and switching to an amd64 Wine-verified
`requirements.txt` remains an explicit known gap rather than an undocumented
inline package list.

### US5 - Reuse heavy image layers and mirror domestically (P2)
**Acceptance**: Source-only releases reuse Wine/Python provisioning from a
persistent registry cache. When mainland registry settings are present, CI
copies the GHCR digest to that registry without a second Docker build.

## Functional Requirements

- **FR-001**: SemVer policy documented; breaking changes to the broker-pack
  contract or exposed tool surface require a major bump plus migration note
  (mirrors the constitution's quality gates).
- **FR-002**: `CHANGELOG.md` in Keep-a-Changelog format with an `Unreleased`
  section seeded from existing history (001–010).
- **FR-003**: `VERSION` file as the single version source of truth.
- **FR-004**: CI validates Conventional Commit subjects and PR titles. `feat`
  bumps minor, breaking changes bump major, and other accepted types bump patch.
- **FR-005**: `.github/workflows/release.yml` starts only after successful
  `main` CI (or manual retry), creates the release commit/tag, builds the amd64
  base image, and pushes `version` plus `latest` to GHCR.
- **FR-006**: qmtctl is cross-built and archived for Linux/macOS/Windows on
  amd64+arm64; all six archives and `SHA256SUMS` are attached to one Release.
- **FR-007**: Release retries are idempotent: an existing tag on HEAD reuses its
  version and rebuilds missing image/assets instead of bumping again.
- **FR-008**: `requirements.in` declares MCP deps; the lockfile generation path
  remains documented and MUST be verified on amd64 before the Dockerfile switches
  to the generated lock.
- **FR-009**: Release notes/changelog never contain secrets.
- **FR-010**: The Dockerfile MUST place stable system/Wine/Python dependency
  layers before frequently changing application source and retain a source-level
  smoke test after the copy.
- **FR-011**: BuildKit MUST import the persistent GHCR registry cache and retain
  the previous GHA cache as a migration fallback.
- **FR-012**: An optional mainland registry mirror MUST receive the exact GHCR
  digest through OCI manifest/layer copying, never a second build.
- **FR-013**: A manual run MUST accept an existing `vX.Y.Z` tag for idempotent
  rebuild/republication using the current workflow implementation and MUST NOT
  move `latest` backward when retrying an older tag.
- **FR-014**: The release job MUST explicitly receive `contents: write` and an
  explicit release token input.

## Success Criteria

- **SC-001**: CI and release workflows parse and their job dependencies are
  coherent; internal PRs do not run duplicate push CI.
- **SC-002**: Release-policy unit tests cover commit validation, bump precedence,
  SemVer increments, release-commit exclusion, and changelog finalization.
- **SC-003**: A merged Conventional Commit produces exactly one release commit,
  one tag, one GHCR version, six qmtctl packages, checksums, and one Release.
- **SC-004**: After one warm build, an MCP source-only change does not execute
  the Wine/Python dependency-provisioning Docker layer.
- **SC-005**: If a mainland mirror is configured, its version tag resolves to
  the same manifest digest published to GHCR.

## Out of Scope / Deferred

- Multi-arch image builds (the appliance is amd64-only by design).
- Signing/SBOM (future hardening).

## Assumptions / Dependencies

- GHCR is authoritative. A mainland mirror is optional and configured only with
  repository variables/secrets.
- The amd64 image build (001) is the artifact; CI here only orchestrates it.
