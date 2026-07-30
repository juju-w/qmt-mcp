# Tasks: Release & Versioning

- [x] T001 `VERSION` file (start at 0.1.0 — pre-1.0, broker pack contract still
  evolving).
- [x] T002 `CHANGELOG.md` (Keep-a-Changelog) with an `Unreleased` section
  summarizing 001–010.
- [x] T003 `.github/workflows/release.yml` builds the amd64 base image, pushes
  GHCR (`version`+`latest`), creates a GitHub Release, and cross-builds qmtctl
  when the Go module exists.
- [x] T004 `appliance/mcp/requirements.in` declaring fastmcp/uvicorn/numpy/
  pandas; document lockfile generation + Dockerfile wiring (verify on amd64).
- [x] T005 Document SemVer policy in CHANGELOG/CONTRIBUTING (breaking = pack
  contract or tool surface change).
- [x] T006 Verify: release.yml YAML valid; VERSION is SemVer; CHANGELOG sections
  present; requirements.in parses.
- [x] T007 Enforce Conventional Commit subjects and PR titles in CI.
- [x] T008 Remove duplicate internal-PR push runs; run push CI on `main` only.
- [x] T009 Add tested SemVer bump and changelog-finalization policy.
- [x] T010 Trigger automatic version commit/tag only after successful `main` CI.
- [x] T011 Package qmtctl for Linux/macOS/Windows on amd64+arm64 with checksums.
- [x] T012 Publish the GHCR image and all CLI assets in one retryable GitHub Release.
- [x] T013 Reorder Dockerfile layers so MCP source does not invalidate Wine and
  Python dependency provisioning.
- [x] T014 Persist a `mode=max` registry cache in GHCR and import the prior GHA
  cache during migration.
- [x] T015 Add optional digest-preserving mainland registry mirroring.
- [x] T016 Add explicit Release permissions/token and current-workflow retries
  for an existing version tag.
