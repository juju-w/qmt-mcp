# Research: OAuth Authorization

## Decision 1: Remain a resource server

**Decision**: QMT MCP validates access tokens but delegates login, consent,
client registration, authorization codes, refresh tokens, and revocation to an
external OAuth authorization server.

**Rationale**: MCP 2026-07-28 defines the MCP server as an OAuth 2.1 resource
server. Adding an authorization server would create a second identity system
and a much larger secret-bearing attack surface.

## Decision 2: Validate asymmetric JWTs against explicit JWKS

**Decision**: Require one exact issuer, one exact RFC 8707 resource audience,
an explicit JWKS URL, `exp`, and an asymmetric algorithm allowlist. Accept
standard `scope` strings and `scp` arrays.

**Rationale**: The existing deployment needs local validation without a
gateway. Explicit URLs avoid token-controlled discovery and reduce SSRF risk.
Opaque token introspection remains a separate future transport.

## Decision 3: Preserve static auth with explicit modes

**Decision**: Keep the current token behavior as the default `static` mode and
add opt-in `oauth` and `hybrid` modes. In hybrid mode, the static deployment
token maps to the startup-visible admin surface while OAuth tokens remain
scope bounded.

**Rationale**: Existing personal and NAS installations should not need an IdP
after upgrading. An explicit mode prevents a partially configured discovery
document from silently changing which credentials are accepted.

## Decision 4: Intersect token scopes with 020 visibility

**Decision**: Require `qmt:read` for all OAuth requests, then add:

| Tool type | Additional scope |
|---|---|
| Core health/capabilities | none |
| Read-only xtdata | `qmt:market` |
| Read-only xttrade/portfolio | `qmt:account` |
| Non-trading mutation | `qmt:manage` plus its family scope |
| All startup-visible tools | `qmt:admin` |

`qmt:admin` does not bypass startup feature gates, allowlists, or denylists.

**Rationale**: Scope filtering is an authorization layer, not a replacement for
operator configuration. Requiring the family plus management scope prevents a
generic management token from exposing account data.

## Decision 5: Use SDK auth context plus a narrow HTTP scope guard

**Decision**: Use the Python SDK `TokenVerifier`, `AuthSettings`, and auth
context for authentication and dynamic `tools/list`/`tools/call` filtering.
Add a bounded HTTP guard for modern `Mcp-Name` calls so insufficient scope can
produce the MCP-required 403 challenge before JSON-RPC dispatch. Handler-level
checks remain authoritative for every era.

**Rationale**: The SDK propagates principals correctly across stateless and
sessionful paths. A handler-only error cannot express the required HTTP
challenge, while a header-only guard cannot secure legacy calls.

## Decision 6: Let the official Go SDK own OAuth protocol details

**Decision**: Build qmtctl login around `auth.AuthorizationCodeHandler`.
Implement only local callback/browser UX and atomic session persistence.
Prefer Client ID Metadata Documents, permit preregistered public clients, and
offer DCR behind an explicit flag.

**Rationale**: The official handler already implements PKCE, protected-resource
and authorization-server discovery, RFC 8707, RFC 9207, refresh, and scope
step-up. Reimplementing those flows would be both less interoperable and less
secure.

## Primary Sources

- MCP 2026-07-28 authorization:
  https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
- RFC 9728 OAuth Protected Resource Metadata:
  https://www.rfc-editor.org/rfc/rfc9728
- RFC 8707 Resource Indicators:
  https://www.rfc-editor.org/rfc/rfc8707
- RFC 9207 Authorization Server Issuer Identification:
  https://www.rfc-editor.org/rfc/rfc9207
- Official Python SDK v2 auth implementation:
  https://github.com/modelcontextprotocol/python-sdk/tree/v2.0.0
- Official Go SDK v1.7 OAuth client:
  https://github.com/modelcontextprotocol/go-sdk/blob/v1.7.0/docs/protocol.md
