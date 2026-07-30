# Verification: MCP Protocol Foundation

**Date**: 2026-07-31

## Runtime and application tests

- `ruff check .`: passed.
- `ruff format --check .`: passed (81 files).
- Python 3.12 unit tier: 150 passed, 1 PostgreSQL test skipped because
  `QMT_TEST_DB_URL` was not configured.
- Python 3.12 official-SDK integration tier: 8 passed.
- `go test ./...`, `go vet ./...`, and `go build ./...`: passed.
- qmtctl cross-compilation passed for Linux, macOS, and Windows on amd64 and
  arm64.

## Official MCP conformance

Runner: `@modelcontextprotocol/conformance@0.2.0-alpha.10`.

Selected server scenarios:

| Era | Scenario | Result |
|---|---|---|
| 2026-07-28 | `tools-list` | 2/2 passed |
| 2026-07-28 | `caching` | 6/6 passed; unavailable resource read skipped |
| 2026-07-28 | `http-header-validation` | 13/13 passed |
| 2025-11-25 | `server-initialize` | 2/2 passed |
| 2025-11-25 | `ping` | 1/1 passed |
| 2025-11-25 | `tools-list` | 2/2 passed |

Selected qmtctl client scenarios:

| Era | Scenario | Result |
|---|---|---|
| 2026-07-28 | `tools_call` | 1/1 passed |
| 2026-07-28 | `request-metadata` | 5/5 applicable checks passed |
| 2026-07-28 | `http-standard-headers` | 3/3 qmtctl-supported checks passed |
| 2025-11-25 | `initialize` | 1/1 passed |
| 2025-11-25 | `tools_call` | 1/1 passed |

No expected-failure file is used. The aggregate `server-stateless` scenario was
explored but is not selected because it requires an application-specific
production tool named `test_missing_capability`. The same-endpoint integration
tests directly verify modern discovery/sessionlessness and legacy
initialize/session behavior without adding a test tool to production.

## Dependency lock

- A clean macOS Python 3.12 environment installed `requirements.txt` with
  `pip --require-hashes`; all direct versions matched the declaration.
- uv hash-verified dry-run resolved the lock for Linux x86_64 Python 3.12
  (33 packages).
- uv hash-verified dry-run resolved the lock for Windows x86_64 Python 3.12
  (36 packages, including Windows markers and wheels).

## Repository checks

- Release-policy unit tests: 7 passed.
- actionlint 1.7.12: passed.
- `git diff --check`: passed.
- Changed-path review confirmed that `.env`, broker files, personal strategies,
  screenshots, and local scripts are not part of this feature.

## Image smoke

The final `linux/amd64` build command is:

```bash
docker buildx build --builder orbstack --platform linux/amd64 \
  --load -t qmt-mcp:019-smoke appliance
```

The local arm64 builder reached the Wine provisioning layer, where the Windows
Python installer exited 139 under amd64 emulation. The NAS was unreachable from
this network. The committed PR/main image job therefore runs the complete
Dockerfile on GitHub's native linux/amd64 runner, including Wine Windows Python
lock installation, SDK import, and application smoke. Its `appliance-ci` GHA
cache is also the release workflow's first cache source.
