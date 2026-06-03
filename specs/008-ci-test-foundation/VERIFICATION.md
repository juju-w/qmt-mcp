# 008 Verification

Date: 2026-06-04 · Host: darwin/arm64, Python 3.12.2 (the lint+unit tier is
platform-agnostic; matches the `ubuntu-latest` CI runner).

## Results

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check .` | ✅ All checks passed |
| Format | `ruff format --check .` | ✅ 27 files formatted |
| Unit tests | `pytest -m 'not integration'` | ✅ 52 passed |
| Integration tier gating | `pytest` | ✅ 1 skipped (no fastmcp), 52 passed |
| SC-004 (real assertions) | broke audit redaction regex → ran the matching test | ✅ test failed (exit 1), reverted |
| CI YAML | `yaml.safe_load(ci.yml)` | ✅ valid |

## Coverage (unit tier, zero third-party runtime deps)

`config` (fail-closed security), `errors` (envelopes/taxonomy), `audit`
(JSONL + secret redaction), `health` (documents/families/`ok` semantics),
`workers` (capacity/timeout), `registry` (no-write guarantee + audit outcomes),
xtdata `validation` + `serializers`.

## Changes landed

- `qmt_mcp_core/__init__.py` → lazy re-exports (PEP 562); pure modules now import
  without `fastmcp`.
- `qmt_mcp_core/errors.py` → registered the `config` startup error type (was
  silently degrading to `internal`; found by `test_config`).
- `qmt-wine-rdp/mcp/pyproject.toml` → ruff + pytest config (E501 owned by
  formatter).
- `qmt-wine-rdp/mcp/tests/` → conftest (fake xtquant, env isolation) + 8 unit
  modules + 1 gated integration module + README.
- `.github/workflows/ci.yml` → lint+format+unit, gitleaks secret scan,
  conditional Go build for qmtctl (007).
- One-time `ruff format` normalization of 6 existing files (format-only).

## Out of scope (recorded)

- Wine/amd64 image build in CI → 011 release pipeline.
- In-image pip dependency pinning (constitution III gap) → 011 (needs an amd64
  build to verify).
- Live xtdata/xttrader integration → manual (broker pack required).

## Not runnable here

- The GitHub Actions run itself (needs a push to GitHub). The non-Wine jobs were
  validated by running their exact commands locally; the `secret-scan` and
  `go-cli` jobs are config-validated only (YAML parse + logic review).
