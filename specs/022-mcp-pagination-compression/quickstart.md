# Quickstart: MCP Pagination and HTTP Compression

Defaults require no migration:

```bash
QMT_MCP_LIST_PAGE_SIZE=50
QMT_MCP_GZIP_MIN_SIZE=1024
```

Disable application gzip when a reverse proxy owns compression:

```bash
QMT_MCP_GZIP_MIN_SIZE=0
```

List the complete authorized catalog; qmtctl follows cursors automatically:

```bash
qmtctl --url https://qmt.example.com/mcp tools
qmtctl --url https://qmt.example.com/mcp --json tools
```

Local verification:

```bash
cd appliance/mcp
ruff check .
ruff format --check .
pytest -m 'not integration'
pytest -m integration

cd ../../cli/qmtctl
go test ./...
go vet ./...
go build ./...
```
