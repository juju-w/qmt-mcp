# Quickstart: Verify MCP 2026-07-28 Only

## Python checks

```bash
cd appliance/mcp
ruff check .
ruff format --check .
pytest -m 'not integration'
pytest -m integration
```

## Go checks

```bash
cd cli/qmtctl
go test ./...
go vet ./...
go build ./...
go build ./cmd/conformance
```

## Modern discovery smoke

Send `server/discover` with `MCP-Protocol-Version: 2026-07-28` and matching
modern `_meta`. Verify `supportedVersions` is exactly `["2026-07-28"]` and the
response has no `Mcp-Session-Id`.

## Legacy rejection smoke

Send a 2025 initialize request without a modern protocol header. Verify HTTP
400, JSON-RPC code `-32022`, `supported: ["2026-07-28"]`, and no
`Mcp-Session-Id`.

## Repository gates

```bash
python -m unittest discover -s .github/scripts -p 'test_*.py'
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/*.yml
git diff --check
```

The PR CI runs the pinned official modern conformance selection and the native
linux/amd64 image smoke. Release automation, not a manual `VERSION` edit,
publishes `1.0.0` after the breaking commit reaches main.
