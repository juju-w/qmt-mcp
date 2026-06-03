# Implementation Plan: CI & Test Foundation

**Branch**: `002-mcp-server-core` (pinned feature dir) | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

## Summary

Make the codebase testable without the appliance, then wire a CI pipeline.
Two-tier tests: a **unit tier** (stdlib + pytest only, the CI default) and an
optional **integration tier** (installs `fastmcp`, injects a fake `xtquant`).
Enable the unit tier by making `qmt_mcp_core/__init__.py` lazy so pure modules
import without `fastmcp`.

## Technical Context

**Language/Version**: Python 3.12 (host + CI), matching the in-Wine runtime major.minor. Go 1.x for the conditional qmtctl build.

**Primary Dependencies (test/CI only)**: `pytest`, `ruff`; `gitleaks` (CI action); `fastmcp` only for the optional integration tier. No `xtquant` ever (faked).

**Storage**: tmp dirs for audit-sink tests; no persistent storage.

**Testing**: `pytest` under `qmt-wine-rdp/mcp/tests/`, unit + integration markers.

**Target Platform**: `ubuntu-latest` GitHub Actions runner for lint/unit/secret; the Wine/amd64 image build is explicitly out of scope here.

**Project Type**: Repo tooling additive to `qmt-wine-rdp/`.

**Constraints**: Unit tier must need no third-party runtime deps; CI must need no secrets/broker pack; never weaken the no-write-tools or fail-closed invariants while testing them.

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| I. Broker-Agnostic Base | Tests use fakes, no broker pack baked or required | PASS |
| II. Read-Only by Default | A test asserts `registry.assert_no_write_tools()` holds | PASS |
| III. Reproducible / Pinned | CI tools pinned via action refs; **in-image pip pin is a known gap** deferred to 011 (needs amd64 build) | PASS (documented deferral) |
| IV. Contract-First MCP | Health/capability/error-envelope contracts get assertions | PASS |
| V. Observable / Auditable | Audit sink + health documents covered by unit tests | PASS |
| VI. Security by Default | Secret scan in CI; auth fail-closed asserted in tests | PASS |
| VII. Spec-Driven | 008 scoped to CI/tests; no feature behavior change beyond the lazy `__init__` | PASS |

## Project Structure

```text
qmt-wine-rdp/mcp/
├── qmt_mcp_core/__init__.py     # MODIFY: lazy re-exports (no fastmcp at import)
├── pyproject.toml               # NEW: ruff + pytest config, markers
└── tests/
    ├── README.md                # NEW: how to run; host scope vs Wine scope
    ├── conftest.py              # NEW: fake xtquant injector, tmp audit fixtures
    ├── unit/
    │   ├── test_config.py
    │   ├── test_errors.py
    │   ├── test_audit.py
    │   ├── test_health.py
    │   ├── test_workers.py
    │   ├── test_registry.py
    │   ├── test_validation.py
    │   └── test_serializers.py
    └── integration/
        └── test_app_asgi.py     # marked; needs fastmcp + fake xtquant

.github/workflows/ci.yml         # NEW: lint + unit + secret-scan + conditional go
```

**Structure Decision**: Tests live beside the package they cover
(`qmt-wine-rdp/mcp/tests/`) with a local `pyproject.toml` so `ruff`/`pytest`
resolve config from there and from repo root. The integration tier is isolated
behind a `@pytest.mark.integration` marker and an `importorskip("fastmcp")`.

## Complexity Tracking

> Not required — Constitution Check passed (in-image pip pinning is an explicit,
> recorded deferral to 011, not an unjustified violation).
