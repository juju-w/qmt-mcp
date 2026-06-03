# Contributing

Thanks for your interest! This is a broker-agnostic QMT-MCP appliance. Please read
`README.md` (overview) and `AGENT.md` (project map + hard-won gotchas) first.

**Help especially wanted**: feature 004 (read-only account-query tools) needs an
account with broker *programmatic-trading permission* (`m_nPythonConnectNet`) to
validate the success paths — the maintainer does not have it. If you do, PRs that
verify 004 are very welcome. Feature 005 (supervision/readiness) is designed and
open for implementation. See `specs/004-*` and `specs/005-*`.

## Ground rules (read before pushing)

This repo is **spec-driven** and **security-sensitive**. Two non-negotiables:

1. **Never commit secrets or broker data.** No tokens, account ids, passwords,
   broker terminals, `xtquant`, or broker packs. `.env` and `brokers/*/pack/` are
   git-ignored — keep it that way. CI runs a secret scan (gitleaks).
2. **Read-only by default.** The MCP exposes no order/cancel/transfer/borrow/
   export tools. Do not add write/trade tools outside an explicitly approved,
   guarded spec (see the constitution, Principle II).

## Desensitization checklist (before every push)

- [ ] No real account ids, tokens, passwords, or broker names tied to a real login.
- [ ] No files under `brokers/*/pack/`, no `.env`, no QMT terminal binaries.
- [ ] Example configs use placeholders (see desensitized `brokers/<id>/broker.yaml`).
- [ ] `git diff` reviewed for pasted logs containing session paths/credentials.

## Spec-driven workflow

Features flow **spec → (clarify) → plan → tasks → implement**, one feature at a
time, under `specs/NNN-feature-name/`. Don't widen an in-flight feature — write a
new spec instead. The constitution lives at `.specify/memory/constitution.md` and
every plan must pass its checks.

- Branch naming: `NNN-feature-name` (e.g. `008-ci-test-foundation`).
- The active feature is pinned in `.specify/feature.json` and mirrored in
  `CLAUDE.md`.

## Development setup & tests

The MCP runtime targets **Windows Python 3.12 under Wine**, but the test suite is
designed to run on a plain host Python 3.12 with no Wine and no broker pack:

```bash
cd appliance/mcp
python3 -m pip install ruff pytest
python3 -m ruff check .
python3 -m ruff format --check .
python3 -m pytest -m 'not integration'
```

See `appliance/mcp/tests/README.md` for the unit vs. integration tiers and
what is intentionally out of host scope (live xtdata/xttrader, the Wine/amd64
image build). Add unit tests for new pure-logic code; keep them dependency-light.

## Commits & PRs

- Use clear, scoped messages; prefix with the feature where useful, e.g.
  `feat(008): ...`, `fix: ...`, `docs: ...`.
- Keep PRs focused; describe what changed and how you verified it.
- CI (lint + format + unit tests + secret scan) must be green.

## Reporting security issues

Do **not** open a public issue. See `SECURITY.md`.

## License

By contributing, you agree your contributions are licensed under the repository's
MIT `LICENSE`.
