# Tasks: Release & Versioning

- [x] T001 `VERSION` file (start at 0.1.0 — pre-1.0, broker pack contract still
  evolving).
- [x] T002 `CHANGELOG.md` (Keep-a-Changelog) with an `Unreleased` section
  summarizing 001–010.
- [x] T003 `.github/workflows/release.yml` — on `v*` tag: build amd64 base image,
  push to GHCR (`version`+`latest`), create GitHub Release; conditional qmtctl
  cross-build when a Go module exists.
- [x] T004 `appliance/mcp/requirements.in` declaring fastmcp/uvicorn/numpy/
  pandas; document lockfile generation + Dockerfile wiring (verify on amd64).
- [x] T005 Document SemVer policy in CHANGELOG/CONTRIBUTING (breaking = pack
  contract or tool surface change).
- [x] T006 Verify: release.yml YAML valid; VERSION is SemVer; CHANGELOG sections
  present; requirements.in parses.
