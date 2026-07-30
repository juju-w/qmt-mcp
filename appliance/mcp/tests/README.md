# QMT MCP tests

Two tiers. The **unit tier** is the CI default and needs no third-party runtime
deps — no `mcp`, no `uvicorn`, no `xtquant`, no Wine, no broker pack. It
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

Exercises app assembly + the ASGI auth/`/healthz` path. It installs official `mcp`
and injects a **fake `xtquant`** (see `conftest.py::fake_xtquant`), so it still
needs no Wine or broker pack. It covers stable/legacy MCP negotiation, OAuth,
durable Tasks, partial task input, MRTR-to-Task composition, and transient
answer handling. Task notification coverage includes the real Streamable HTTP
SSE transport, acknowledgement/current/terminal ordering, mixed filters,
backpressure, reconnect state, and OAuth isolation. It is skipped automatically
when `mcp` is absent.

```bash
python3 -m pip install "mcp==2.0.0"
python3 -m pytest -m integration
```

CI additionally runs the pinned official MCP conformance package, including
the 023 Tasks lifecycle scenarios plus `tasks-mrtr-input` and
`tasks-mrtr-composition`. CI also invokes `tasks-status-notifications`; pinned
conformance alpha.10 currently reports that scenario pending, so the project
integration tests remain its executable gate. Synthetic tools are available only when
`QMT_MCP_TASK_CONFORMANCE_FIXTURES=1`.

## Intentionally out of host scope

These need the real appliance and stay manual (see each feature's `quickstart.md`
and `VERIFICATION.md`):

- Live `xtdata` reads against a logged-in QMT terminal.
- `xttrader` connect / account queries (need broker programmatic permission).
- The Wine/amd64 image build and in-Wine smoke tests.
