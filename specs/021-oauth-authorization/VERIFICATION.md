# Verification: OAuth Authorization

Date: 2026-07-31

## Local evidence

- Python lint and formatting: `ruff check` and `ruff format --check` passed.
- Python dependency-light CI environment: 192 passed and 3 skipped (the
  database and two runtime-only integration modules).
- Python full-runtime unit selection: 192 passed, 1 database test skipped, and
  20 integration tests deselected.
- Python integration suite: 20 passed and 193 tests were deselected.
- Go: `go test -race ./...`, `go vet ./...`, `go build ./...`, and the
  conformance client build passed.
- Cross-compilation: qmtctl built for Darwin, Linux, and Windows on both amd64
  and arm64.
- Release policy: 7 tests passed.
- Workflow validation: actionlint passed.
- Compose validation: static-token, OAuth-only, and OAuth-over-TLS
  configurations rendered successfully.
- Shell validation: entrypoint and hardening scripts passed Bash syntax checks.
- Diff validation: `git diff --check` passed.

## Official conformance

The selected MCP 2026-07-28 primary and 2025-11-25 compatibility suites passed:

| Target | Protocol | Suites | Result |
| --- | --- | --- | --- |
| Server | 2026-07-28 | tools list, caching, headers | 21 passed |
| Server | 2025-11-25 | initialize, ping, tools list | 5 passed |
| qmtctl | 2026-07-28 | tools call, request metadata, headers | 9 passed |
| qmtctl | 2025-11-25 | initialize, tools call | 2 passed |

The optional resource-read case was skipped because this server does not expose
MCP resources.

## Security coverage

- JWT signature, issuer, string/array audience, expiration, not-before,
  required expiration, algorithm allowlist, malformed scopes, JWKS rotation,
  duplicate keys, response bounds, redirect rejection, and fetch backoff.
- Standard RFC 9728 metadata and minimal 401/403 challenges.
- Base `qmt:read` enforcement, per-tool scope filtering, direct call
  enforcement, profile intersections, and hybrid static/OAuth behavior.
- qmtctl PKCE, Client ID Metadata Documents, preregistered public clients,
  explicit DCR compatibility, callback validation, refresh rotation, saved
  session step-up, redacted status, selective logout, concurrent writers, and
  explicit bearer precedence.

## Pending remote evidence

T029 and T030 remain open until the pull request passes GitHub secret scanning
and the native Linux amd64 appliance image build. The final check and release
links will be recorded here after CI completes.
