# Tasks: Production MCP Server Core

**Feature**: 002-mcp-server-core | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Paths are relative to repo root. Implementation lives in `appliance/`.

## Phase 1: Setup

- [x] T001 Create MCP core package scaffold in `appliance/mcp/qmt_mcp_core/` with `__init__.py`, `config.py`, `errors.py`, `audit.py`, `health.py`, `registry.py`, `workers.py`, and `app.py`.
- [x] T002 Add a core smoke script in `appliance/mcp/qmt_mcp_core/smoke.py` that can run without QMT login.
- [x] T003 Update `appliance/Dockerfile` build-time smoke to import `qmt_mcp_core` and validate the core registry has no write/trade tools.

## Phase 2: Foundational

- [x] T004 Implement resolved MCP config loading in `appliance/mcp/qmt_mcp_core/config.py` from `/opt/qmt-mcp/mcp.env` and environment variables.
- [x] T005 Implement uniform `ErrorEnvelope` helpers in `appliance/mcp/qmt_mcp_core/errors.py`.
- [x] T006 Implement append-only JSONL audit sink in `appliance/mcp/qmt_mcp_core/audit.py` with secret/argument sanitization.
- [x] T007 Implement capability state models and health snapshot assembly in `appliance/mcp/qmt_mcp_core/health.py`.
- [x] T008 Implement explicit tool registry and family gating in `appliance/mcp/qmt_mcp_core/registry.py`.
- [x] T009 Implement bounded worker executor and capacity errors in `appliance/mcp/qmt_mcp_core/workers.py`.
- [x] T010 Replace pass-through logic in `appliance/mcp/qmt_mcp.py` with the new core app entrypoint while preserving Wine launch compatibility.

**Checkpoint**: MCP core imports, starts, rejects accidental write tools, and can run without QMT login.

## Phase 3: User Story 1 - Guarded MCP Endpoint (P1)

**Goal**: authenticated agents can connect/discover; unauthenticated clients are rejected.

**Independent test**: start MCP with no QMT login; unauthenticated `/healthz` and `/mcp` fail; authenticated health/discovery succeeds; no write tools appear. SSE is tested only when `QMT_MCP_TRANSPORT=sse` is explicitly set.

- [x] T011 [US1] Implement bearer-token ASGI middleware in `appliance/mcp/qmt_mcp_core/app.py`.
- [x] T012 [US1] Enforce fail-closed behavior when `QMT_MCP_TOKEN` is empty on non-loopback bind in `appliance/mcp/qmt_mcp_core/config.py`.
- [x] T013 [US1] Register core tools `qmt_health` and `qmt_capabilities` in `appliance/mcp/qmt_mcp_core/registry.py`.
- [x] T014 [US1] Ensure tool discovery only exposes explicit registered tools in `appliance/mcp/qmt_mcp_core/app.py`.
- [x] T015 [US1] Add a smoke check in `appliance/mcp/qmt_mcp_core/smoke.py` for auth-required config, core tool registration, and absence of write tools.

**Checkpoint**: MVP guarded MCP core is usable before QMT login.

## Phase 4: User Story 2 - Health And Auditability (P2)

**Goal**: operators can see health/capabilities and every accepted call is audited.

**Independent test**: authenticated health returns stable state; accepted core tool calls append JSONL records with sanitized args and no token leakage.

- [x] T016 [US2] Implement `/healthz` HTTP route matching `specs/002-mcp-server-core/contracts/health.md` in `appliance/mcp/qmt_mcp_core/app.py`.
- [x] T017 [US2] Implement `qmt_capabilities` output matching `contracts/tool-catalog.md` in `appliance/mcp/qmt_mcp_core/health.py`.
- [x] T018 [US2] Wire audit logging around every accepted tool invocation in `appliance/mcp/qmt_mcp_core/registry.py`.
- [x] T019 [US2] Add audit sink initialization/fail-closed checks in `appliance/mcp/qmt_mcp_core/audit.py`.
- [x] T020 [US2] Add smoke assertions in `appliance/mcp/qmt_mcp_core/smoke.py` that audit records are JSONL and sanitized.

## Phase 5: User Story 3 - Responsiveness Under Blocking Work (P2)

**Goal**: slow worker-backed operations do not block health or discovery.

**Independent test**: run a simulated slow tool; authenticated health responds before the slow call finishes; capacity limit returns a uniform error.

- [ ] T021 [US3] Add a development-only simulated slow worker tool guarded behind test/smoke config in `appliance/mcp/qmt_mcp_core/smoke.py`.
- [x] T022 [US3] Route worker-backed tool calls through `appliance/mcp/qmt_mcp_core/workers.py`.
- [x] T023 [US3] Implement capacity-limit error mapping in `appliance/mcp/qmt_mcp_core/errors.py`.
- [ ] T024 [US3] Add concurrency smoke checks in `appliance/mcp/qmt_mcp_core/smoke.py`.

## Phase 6: Polish & Cross-Cutting

- [x] T025 Update `appliance/scripts/start-mcp.sh` to log core config summary and audit path without secrets.
- [ ] T026 Update `appliance/README.md` with MCP core auth/health/audit usage.
- [ ] T027 Update `appliance/docs/BROKER-PACK.md` to mention JSONL audit location and xttrade disabled/not_authorized semantics.
- [ ] T028 Run `specs/002-mcp-server-core/quickstart.md` on a native amd64 host and record results.
- [ ] T029 Verify success criteria SC-001..SC-006 from `specs/002-mcp-server-core/spec.md`.

## Dependencies & Order

- Phase 1 -> Phase 2 -> US1 -> US2/US3 -> Polish.
- US1 is MVP and blocks 003 because xtdata tools need auth, registry, health, audit, and worker infrastructure.
- US2 and US3 can proceed after foundational work; they touch mostly distinct modules.

## MVP Scope

T001-T015: package scaffold, config/errors/audit/health/registry/worker basics,
new app entrypoint, bearer auth, core tools, and smoke checks. This produces a
guarded MCP core with no business tools and no QMT login requirement.
