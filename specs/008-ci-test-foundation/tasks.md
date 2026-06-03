# Tasks: CI & Test Foundation

Legend: `[ ]` todo · `[x]` done. [P] = parallelizable.

## Phase A — Enable host-runnable imports
- [x] T001 Make `qmt_mcp_core/__init__.py` lazy (PEP 562 `__getattr__`) so the
  package imports without `fastmcp`; preserve `create_app`/`main`/`ToolRegistry`.
- [x] T002 Verify each pure module imports standalone on host Python
  (`config,errors,audit,health,workers,registry,validation,serializers`).

## Phase B — Test tooling config
- [x] T003 Add `qmt-wine-rdp/mcp/pyproject.toml` with `[tool.ruff]` (line length,
  target py312, sensible rule set) and `[tool.pytest.ini_options]` (testpaths,
  markers: `integration`).
- [x] T004 Add `tests/conftest.py`: fake-`xtquant` injector fixture (sys.modules),
  tmp audit-path fixture, and an autouse env-isolation fixture.

## Phase C — Unit tests (stdlib + pytest only) [P]
- [x] T005 `test_config.py` — env parsing, defaults, `validate_security`
  fail-closed (no token on non-loopback raises; loopback+allow ok), transport
  validation.
- [x] T006 `test_errors.py` — `error_envelope`/`from_exception` shape + types.
- [x] T007 `test_audit.py` — JSONL append, initialize, no-secret fields, ordering.
- [x] T008 `test_health.py` — `to_dict`/`capabilities` keys, family states,
  `ok` semantics, `set_family`/`update_family_tools`.
- [x] T009 `test_workers.py` — capacity exhaustion raises `capacity`; timeout maps
  to `dependency`; successful run returns value.
- [x] T010 `test_registry.py` — `assert_no_write_tools` passes for read-only set;
  detects a planted write-tool name; audit wrapper records outcome.
- [x] T011 `test_validation.py` — symbol/period/date validators accept valid,
  reject invalid with `McpCoreError`.
- [x] T012 `test_serializers.py` — structured outputs, datetime handling, no raw
  SDK passthrough.

## Phase D — Integration tier (optional, gated)
- [x] T013 `tests/integration/test_app_asgi.py` — `importorskip('fastmcp')`,
  inject fake `xtquant`, build app, assert `/healthz` 401 without token + 200 with
  token, `/livez` shape (once 005 lands), and no write tools registered.

## Phase E — CI pipeline
- [x] T014 `.github/workflows/ci.yml` — jobs: (1) lint+unit on ubuntu (pip install
  ruff pytest; ruff check; pytest -m 'not integration'); (2) secret-scan
  (gitleaks action); (3) conditional go build (`if` qmtctl module exists).
- [x] T015 `tests/README.md` — run instructions + host-vs-Wine scope note.

## Phase F — Verify
- [x] T016 Run `ruff check` and `pytest -m 'not integration'` locally; both green.
- [x] T017 Confirm SC-004: break one invariant, see the matching test fail, revert.
- [x] T018 Validate `ci.yml` YAML parses and commands mirror local ones.
