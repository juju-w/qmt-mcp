# Tasks: OAuth Authorization

## Phase 1 - Specification and policy

- [x] T001 Record auth-mode, JWT/JWKS, scope, and client-flow decisions.
- [x] T002 Define protected-resource, challenge, and tool-scope contracts.
- [x] T003 Add dependency-light tests for auth configuration and scope policy.

## Phase 2 - Server authentication

- [x] T004 Add static/oauth/hybrid configuration with fail-closed validation.
- [x] T005 Implement bounded JWKS retrieval and asymmetric JWT verification.
- [x] T006 Map verified claims into the official SDK access-token context.
- [x] T007 Wire SDK resource-server auth and RFC 9728 metadata routes.
- [x] T008 Preserve static bearer and unauthenticated loopback compatibility.
- [x] T009 Protect health while keeping minimal liveness public.

## Phase 3 - Tool authorization

- [x] T010 Attach required OAuth scopes to every registered tool.
- [x] T011 Filter `tools/list` by the verified request principal.
- [x] T012 Independently enforce scopes on every `tools/call`.
- [x] T013 Return modern 403 scope step-up challenges at the HTTP boundary.
- [x] T014 Preserve execution-safe legacy calls and startup-profile
  intersections.

## Phase 4 - qmtctl OAuth

- [x] T015 Add an atomic, permission-checked per-resource OAuth session store.
- [x] T016 Add browser/printed URL and loopback callback handling.
- [x] T017 Configure official SDK PKCE for Client ID Metadata Documents.
- [x] T018 Add preregistered-client and explicit DCR compatibility.
- [x] T019 Persist access/refresh rotation and restore sessions automatically.
- [x] T020 Add `auth login`, `auth status`, and `auth logout`.
- [x] T021 Preserve discover and explicit bearer precedence.

## Phase 5 - Tests and documentation

- [x] T022 Test JWT signature, issuer, audience, time, algorithm, JWKS rotation,
  and redaction.
- [x] T023 Test scope matrices and standard 401/403 challenges in modern and
  legacy paths.
- [x] T024 Test qmtctl login, callback validation, persistence, refresh,
  step-up, status, logout, and bearer precedence.
- [x] T025 Update env/compose/deployment, MCP client, CLI, AGENT, and skill docs.

## Phase 6 - Verification and delivery

- [x] T026 Run ruff and Python unit/integration tests.
- [x] T027 Run Go test/vet/build and six-target cross-compilation.
- [x] T028 Run selected modern/legacy official conformance.
- [ ] T029 Run release-policy tests, actionlint, diff/secret review, and native
  linux/amd64 appliance build.
- [ ] T030 Record evidence in `VERIFICATION.md` and close tasks accurately.
