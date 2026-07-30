# Feature Specification: OAuth Authorization

**Feature Branch**: `codex/021-oauth-authorization`

**Created**: 2026-07-31

**Status**: Approved

**Depends on**: 019 (MCP protocol foundation), 020 (tool contracts and
profiles).

## Summary

Turn the existing OAuth discovery scaffold into a complete MCP OAuth 2.1
resource server. Validate externally issued JWT access tokens against a pinned
issuer, audience, expiry, algorithm allowlist, and cached JWKS. Filter listed
and callable tools by token scope, return standard scope step-up challenges,
and keep static bearer deployments backward compatible.

Add qmtctl authorization-code login with PKCE, Client ID Metadata Documents as
the preferred registration path, preregistered clients and deprecated dynamic
registration as compatibility paths, refresh-token persistence, status, and
logout. The server never becomes an authorization server and never receives an
upstream provider token through token passthrough.

MCP `2026-07-28` is the documented and tested primary protocol. Supported 2025
revisions remain automatic same-endpoint compatibility paths.

## User Scenarios & Testing

### User Story 1 - External OAuth tokens are validated locally (Priority: P1)

An operator protects the public MCP endpoint with an external OAuth
authorization server without adding a custom validation gateway.

**Independent Test**: Start the broker-neutral server with a local test JWKS,
send valid and invalid JWTs, and verify protected-resource metadata plus
fail-closed token validation.

**Acceptance Scenarios**:

1. **Given** a signed JWT with the configured issuer, resource audience,
   expiry, allowed algorithm, and base scope, **when** it calls `/mcp` or
   `/healthz`, **then** the request is authenticated.
2. **Given** a token with an unknown key, bad signature, wrong issuer, wrong
   audience, missing/expired expiry, disallowed algorithm, or malformed scope,
   **when** it calls a protected endpoint, **then** it receives 401 without
   leaking validation details.
3. **Given** key rotation at the configured JWKS URL, **when** a new `kid`
   appears, **then** the verifier refreshes its bounded cache and accepts the
   new valid key without restarting.
4. **Given** OAuth mode, **when** metadata is requested, **then** RFC 9728
   metadata names the exact resource, issuer, supported scopes, and header
   bearer method and is available at both standard path forms.

---

### User Story 2 - Tool access follows least-privilege scopes (Priority: P1)

An authorization server can grant market, account, or local-management access
without exposing unrelated tools.

**Independent Test**: List and call tools with tokens carrying each scope
combination through modern and legacy MCP paths.

**Acceptance Scenarios**:

1. **Given** only `qmt:read`, **when** a client lists tools, **then** it sees
   only core health and capability tools allowed by the startup profile.
2. **Given** `qmt:read qmt:market`, **when** it lists tools, **then** read-only
   xtdata tools become visible while account and mutation tools remain hidden.
3. **Given** `qmt:read qmt:account`, **when** it lists tools, **then**
   xttrade-query and portfolio tools become visible while market and mutation
   tools remain hidden.
4. **Given** the matching family scope plus `qmt:manage`, **when** it lists
   tools, **then** non-trading subscription/cache/download/sector/formula
   mutation tools in that family become visible.
5. **Given** `qmt:read qmt:admin`, **when** it lists tools, **then** every tool
   permitted by startup feature gates and profile policy is visible.
6. **Given** an insufficient token calling a known tool, **when** the server can
   identify the tool at the HTTP boundary, **then** it returns 403 with
   `insufficient_scope`, the minimal missing scope, resource metadata URL, and
   resource identifier.

---

### User Story 3 - Existing static-token deployments keep working (Priority: P1)

An existing NAS or local deployment upgrades without having to deploy an OAuth
authorization server.

**Independent Test**: Run existing static bearer, unauthenticated loopback, and
OAuth integration tests under explicit and default auth modes.

**Acceptance Scenarios**:

1. **Given** no auth-mode setting and a `QMT_MCP_TOKEN`, **when** the service
   starts, **then** behavior is identical to v0.6.0 static bearer auth.
2. **Given** `hybrid`, **when** either the configured static token or a valid
   OAuth JWT is supplied, **then** the static token receives startup-visible
   admin access and the JWT receives scope-bounded access.
3. **Given** OAuth configuration is incomplete or insecure, **when** the
   service starts on a non-loopback address, **then** startup fails closed.
4. **Given** an explicitly opted-in loopback development server, **when** no
   token is configured, **then** unauthenticated development remains available
   and scope filtering is not applied.

---

### User Story 4 - qmtctl can complete and retain OAuth login (Priority: P1)

An operator logs in through a browser once and qmtctl refreshes and reuses the
session for later commands.

**Independent Test**: Run qmtctl against an in-process OAuth fixture for
authorization-code + PKCE, refresh, scope step-up, persistence, status, and
logout.

**Acceptance Scenarios**:

1. **Given** a configured Client ID Metadata Document or preregistered public
   client, **when** `qmtctl auth login` runs, **then** it opens or prints the
   authorization URL, verifies callback state and issuer, exchanges the code
   with PKCE and the RFC 8707 resource, and stores the resulting session.
2. **Given** an authorization server that only supports dynamic registration,
   **when** compatibility mode is explicitly selected, **then** qmtctl can
   register and log in without making DCR the recommended path.
3. **Given** a saved refresh token, **when** an access token expires or the
   server requests additional scope, **then** the official Go SDK refreshes or
   steps up and the rotated session is persisted.
4. **Given** `qmtctl auth status` or `auth logout`, **when** run for a resource,
   **then** status never prints token material and logout removes only that
   resource's saved session.
5. **Given** an explicit `--token`, `--access-token`, or matching environment
   variable, **when** any command runs, **then** that explicit bearer takes
   precedence over a saved OAuth session.

## Edge Cases

- Authorization-server metadata lacks PKCE S256, an authorization endpoint, or
  a token endpoint.
- The OAuth callback contains an error, wrong state, wrong RFC 9207 issuer, or
  arrives after timeout.
- The configured JWKS URL is unavailable, slow, oversized, redirects to an
  unsafe scheme, or returns duplicate/unsupported keys.
- A JWT has `aud` as either a string or array and `scope` as a string or `scp`
  as an array.
- A modern request supplies a mismatched `Mcp-Name`; the protocol header
  mismatch remains a protocol error rather than an authorization oracle.
- A legacy tools call has no modern routing header; handler-level enforcement
  still prevents execution even if HTTP step-up cannot be emitted.
- Startup profiles, allowlists, denylists, optional gates, and token scopes
  overlap; every layer is an intersection and deny remains final.
- Multiple qmtctl processes update one session file concurrently.

## Requirements

### Functional Requirements

- **FR-001**: The server MUST support `static`, `oauth`, and `hybrid` auth modes;
  an unset mode MUST preserve v0.6.0 static-token behavior.
- **FR-002**: OAuth and hybrid modes MUST use the official MCP Python SDK auth
  context and an external authorization server; the QMT server MUST NOT issue
  tokens or implement an authorization endpoint.
- **FR-003**: OAuth JWT validation MUST require a configured issuer, exact
  resource audience, future expiry, allowed asymmetric signature algorithm,
  and a successfully resolved JWKS signing key.
- **FR-004**: Validation MUST reject unsigned, HMAC, malformed, expired,
  not-yet-valid, wrong-issuer, wrong-audience, and unknown-key tokens.
- **FR-005**: JWKS retrieval MUST use an explicit HTTPS URL, bounded timeout
  and response size, cache keys, refresh on unknown `kid`, and never perform
  arbitrary issuer discovery at token-validation time.
- **FR-006**: Protected Resource Metadata MUST follow RFC 9728 and MCP
  2026-07-28, advertise the exact RFC 8707 resource and supported scopes, and
  include CORS for browser clients.
- **FR-007**: Unauthenticated or invalid tokens MUST receive 401 with a
  resource-metadata challenge; insufficient scope MUST receive 403 with
  `insufficient_scope`, minimal required scope, resource metadata, and resource.
- **FR-008**: Scope policy MUST support `qmt:read`, `qmt:market`,
  `qmt:account`, `qmt:manage`, and `qmt:admin` and MUST intersect with the 020
  startup visibility policy.
- **FR-009**: `tools/list` MUST expose only tools authorized for the current
  token and `tools/call` MUST independently enforce the same policy.
- **FR-010**: `qmt:manage` MUST NOT independently grant account access or any
  trade/order capability; the repository's no-write assertion remains binding.
- **FR-011**: Static tokens accepted in static or hybrid mode MUST preserve the
  startup-visible tool surface and MUST NOT be serialized into logs, metadata,
  capability payloads, or errors.
- **FR-012**: qmtctl MUST use the official Go SDK OAuth handler for PKCE,
  authorization-server discovery, RFC 8707 resource indicators, RFC 9207
  issuer validation, refresh, and scope step-up.
- **FR-013**: qmtctl MUST prefer Client ID Metadata Documents, support
  preregistered clients, and support DCR only as an explicit compatibility
  option.
- **FR-014**: qmtctl MUST provide `auth login`, `auth status`, `auth logout`,
  and retain `auth discover`.
- **FR-015**: qmtctl OAuth sessions MUST be keyed by canonical resource, stored
  under the user configuration directory with directory mode 0700 and file
  mode 0600, written atomically, and never printed by status or errors.
- **FR-016**: An explicit qmtctl bearer MUST take precedence over persisted
  OAuth; absence of both MUST retain the current unauthenticated request path.
- **FR-017**: OAuth behavior MUST work with preferred MCP `2026-07-28`; static
  auth and scope enforcement MUST regress supported 2025 clients on the same
  endpoint.
- **FR-018**: Unit and integration tests MUST use local keys and local HTTP
  fixtures and MUST NOT require NAS, QMT, broker credentials, or a public IdP.
- **FR-019**: Documentation MUST provide external-AS setup, scope mapping,
  qmtctl login, and Codex/Claude Code/WorkBuddy connection guidance without
  presenting unsupported client behavior as verified.

## Key Entities

- **Auth Mode**: Static bearer, external OAuth JWT, or hybrid acceptance policy.
- **OAuth Principal**: Client id, issuer, optional subject, scopes, resource,
  and bounded non-secret claims derived from a verified access token.
- **Tool Scope Policy**: Required base/family/management scopes for a registered
  tool, intersected with startup visibility.
- **OAuth Session**: qmtctl authorization-server endpoints, client
  registration, scopes, access/refresh token state, and canonical resource.

## Success Criteria

- **SC-001**: All positive JWT fixtures authenticate and every invalid
  issuer/audience/signature/time/algorithm fixture fails closed.
- **SC-002**: Scope-matrix tests prove no market, account, or mutation tool is
  listed or executed without its required scopes.
- **SC-003**: Modern insufficient-scope calls receive standard 403 challenges;
  legacy calls remain execution-safe.
- **SC-004**: qmtctl end-to-end fixture tests pass login, persisted reuse,
  refresh rotation, status redaction, logout, and explicit-token precedence.
- **SC-005**: Existing Python, Go, modern/legacy conformance, actionlint,
  cross-build, and native linux/amd64 appliance gates remain green.

## Out of Scope

- Running an OAuth authorization server, user database, consent UI, or token
  exchange service inside QMT MCP.
- Opaque-token introspection, mutual TLS, DPoP, enterprise identity assertion,
  or upstream token passthrough.
- Client-secret storage in qmtctl; confidential clients should use a dedicated
  secret manager or gateway.
- Trade/order/transfer scopes or tools.
- MCP pagination/compression (022), Tasks (023), Apps (024), Resources and
  Registry publication (025).

## Assumptions

- MCP `2026-07-28` is the latest stable protocol at implementation time.
- Official Python MCP SDK 2.0.0 and Go SDK 1.7.0 remain the reviewed baselines.
- The external authorization server can issue asymmetric JWT access tokens
  with a stable issuer, audience, expiry, key id, and MCP scopes.
