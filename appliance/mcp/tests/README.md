# QMT MCP tests

Two tiers. The **unit tier** is the CI default and needs no third-party runtime
deps — no `fastmcp`, no `uvicorn`, no `xtquant`, no Wine, no broker pack. It
covers the pure-logic modules (`config`, `errors`, `audit`, `health`, `workers`,
`registry`, and the xtdata `validation`/`serializers`).

## Run

```bash
cd appliance/mcp
python3 -m pip install pytest ruff          # only these two for the unit tier
python3 -m ruff check .
python3 -m pytest -m 'not integration'
```

## Integration tier (optional)

Exercises app assembly + the ASGI auth/`/healthz` path. It installs `fastmcp`
and injects a **fake `xtquant`** (see `conftest.py::fake_xtquant`), so it still
needs no Wine or broker pack. It is skipped automatically when `fastmcp` is
absent.

```bash
python3 -m pip install fastmcp
python3 -m pytest -m integration
```

## Intentionally out of host scope

These need the real appliance and stay manual (see each feature's `quickstart.md`
and `VERIFICATION.md`):

- Live `xtdata` reads against a logged-in QMT terminal.
- `xttrader` connect / account queries (need broker programmatic permission).
- The Wine/amd64 image build and in-Wine smoke tests.
