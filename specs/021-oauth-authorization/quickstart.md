# Quickstart: OAuth Authorization

## Static compatibility

No migration is required for an existing deployment:

```bash
QMT_MCP_TOKEN='<existing-random-token>'
```

An unset `QMT_MCP_AUTH_MODE` means `static`.

## External OAuth JWT mode

```bash
QMT_MCP_AUTH_MODE=oauth
QMT_MCP_PUBLIC_BASE_URL=https://qmt.example.com
QMT_MCP_OAUTH_ISSUER=https://auth.example.com
QMT_MCP_OAUTH_AUTHORIZATION_SERVERS=https://auth.example.com
QMT_MCP_OAUTH_JWKS_URL=https://auth.example.com/.well-known/jwks.json
QMT_MCP_OAUTH_RESOURCE=https://qmt.example.com/mcp
QMT_MCP_OAUTH_SCOPES='qmt:read qmt:market qmt:account qmt:manage qmt:admin'
QMT_MCP_OAUTH_ALGORITHMS='RS256 ES256'
```

The authorization server must issue an asymmetric JWT access token with the
configured issuer, resource audience, expiry, client identity, and scopes.

## qmtctl browser login

Preferred Client ID Metadata Document:

```bash
qmtctl --url https://qmt.example.com/mcp auth login \
  --client-id-metadata-url https://client.example.com/qmtctl.json \
  --scope 'qmt:read qmt:market'
```

Inspect and remove the saved resource session:

```bash
qmtctl --url https://qmt.example.com/mcp auth status
qmtctl --url https://qmt.example.com/mcp auth logout
```

An explicit static or access token always wins:

```bash
QMT_MCP_ACCESS_TOKEN='<token>' qmtctl --url https://qmt.example.com/mcp tools
```

## Local tests

```bash
cd appliance/mcp
ruff check .
ruff format --check .
pytest -m 'not integration'
pytest -m integration

cd ../../cli/qmtctl
go test ./...
go vet ./...
```
