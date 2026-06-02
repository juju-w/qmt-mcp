# Tasks: Broker-Agnostic Base Image + Broker Pack

**Feature**: 001-broker-pack-base | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Paths are relative to repo root. The deployable app lives in `qmt-wine-rdp/`.
Tests are lightweight contract/smoke checks (no unit-test framework requested).

## Phase 1: Setup

- [x] T001 Create directory scaffold: `qmt-wine-rdp/brokers/template/`, `qmt-wine-rdp/brokers/guangda-jinyangguang/`, `qmt-wine-rdp/docs/` (keep `brokers/*/pack/` gitignored).
- [x] T002 Update `qmt-wine-rdp/.dockerignore` and root `.gitignore` to exclude broker packs (`qmt-wine-rdp/brokers/*/pack/`) and keep `.env` excluded.

## Phase 2: Foundational (blocks all user stories)

- [x] T003 Refactor `qmt-wine-rdp/Dockerfile` to a broker-neutral base: REMOVE setup_qmt download/7z-extract, REMOVE xtquant download/unrar/site-packages copy, REMOVE the build-time `import xtquant` smoke test and the wineuser provisioning steps that depend on the pack. KEEP: apt (fonts, p7zip-full, unrar, ca-certs) + `python3`+`python3-yaml`, Python 3.12 install into the Wine prefix, CJK fonts into Wine Fonts, pip `fastmcp uvicorn`, MCP launcher COPY + autostart, wineuser creation. Pin versions.
- [x] T004 Adjust the build-time smoke test in `qmt-wine-rdp/Dockerfile` to `import fastmcp` + `qmt_mcp.filter_trade_tools()` only (no xtquant).
- [x] T005 Create `qmt-wine-rdp/scripts/detect-broker.py` (Python 3, Linux): read `/broker/broker.yaml`, validate schema_version/mcp.mode, resolve client/userdata/xtquant with explicit-path precedence, convert to Wine paths via `winepath -w`, write `/run/qmt/broker.env`, log resolution. (Auto-detect + full fail-fast added in US2/US3; here implement explicit-path resolution + write + happy path.)
- [x] T006 Edit `qmt-wine-rdp/scripts/qmt-entrypoint.sh` to run `detect-broker.py` before `exec /usr/bin/entrypoint`; abort (propagate non-zero) on failure; fold resolved keys into `/opt/qmt-mcp/mcp.env`.
- [x] T007 Edit `qmt-wine-rdp/scripts/start-qmt.sh` to launch the client from `QMT_CLIENT_WIN`/`QMT_BIN_DIR_WIN` (resolved env) instead of the hardcoded baked path.
- [x] T008 Edit `qmt-wine-rdp/scripts/start-mcp.sh` and `qmt-wine-rdp/mcp/qmt_mcp.py` to read `QMT_XTQUANT_DIR_WIN` (prepend to `sys.path`) and `QMT_USERDATA_WIN` (trader path) from the resolved env; remove assumptions about baked `C:\workspace\...`.
- [x] T009 Edit `qmt-wine-rdp/scripts/verify-xtquant.sh` to import xtquant from the pack via `QMT_XTQUANT_DIR_WIN`.
- [x] T010 Build the base image on the native amd64 NAS; confirm it builds with NO xtquant/terminal and the build-time smoke (`fastmcp` + filter) passes.

**Checkpoint**: base image exists and builds; resolved-env plumbing wired (not yet auto-detecting).

## Phase 3: User Story 1 — Switch broker by swapping the pack (P1) 🎯 MVP

**Goal**: run a broker by mounting a pack; switch brokers with no rebuild; run multiple instances.

**Independent test**: mount pack A (with explicit `broker.yaml`), container starts & resolves & RDP up; swap to pack B, same image, starts driving B; two instances run concurrently.

- [x] T011 [US1] Rewrite `qmt-wine-rdp/docker-compose.yml`: mount `${BROKER_PACK}:/broker` read-write; parameterize `container_name`, RDP/MCP host ports, and `QMT_MCP_TOKEN` from `.env`; drop baked-workspace assumptions.
- [x] T012 [P] [US1] Create `qmt-wine-rdp/scripts/make-broker-pack.sh <setup_qmt.exe> <xtquant.rar> <out-dir>`: 7z-extract the terminal + unrar xtquant into out-dir and drop a starter `broker.yaml`.
- [x] T013 [US1] Create `qmt-wine-rdp/brokers/guangda-jinyangguang/broker.yaml` example (光大金阳光) with explicit paths.
- [ ] T014 [US1] On the NAS, build a 金阳光 pack with `make-broker-pack.sh` (reuse the already-downloaded setup_qmt.exe + xtquant rar), mount it, `docker compose up -d`, verify resolution + RDP reachable.
- [ ] T015 [US1] Verify switch: bring down, point `BROKER_PACK` at a second pack dir, `up -d` with the same image tag (no build), confirm it drives the second pack.
- [ ] T016 [US1] Verify two instances concurrently (distinct ports/tokens/packs) run without interference.

**Checkpoint**: MVP — broker swap works with explicit `broker.yaml`.

## Phase 4: User Story 2 — First-time setup with auto-detection (P2)

**Goal**: a standard-layout pack starts with empty/minimal `broker.yaml`.

**Independent test**: pack with standard layout + no `broker.yaml` starts via auto-detection; explicit override changes the resolved value.

- [x] T017 [US2] Implement auto-detection in `detect-broker.py`: client by known names (`XtItClient.exe`,`XtMiniQmt.exe`), `userdata_mini` dir, `xtquant/__init__.py` dir; explicit value still wins.
- [x] T018 [P] [US2] Create `qmt-wine-rdp/brokers/template/broker.yaml` (documented, all-optional template).
- [ ] T019 [US2] On the NAS, verify a pack with NO `broker.yaml` resolves and starts via auto-detection; verify an explicit `terminal.client` override is honored.

**Checkpoint**: low-friction onboarding via auto-detection.

## Phase 5: User Story 3 — Fail fast and clearly on a bad pack (P2)

**Goal**: incomplete/ambiguous packs refuse to start with specific messages and non-zero exit; nothing left listening.

**Independent test**: empty mount, missing xtquant, ambiguous client each exit with a distinct message and no RDP/MCP up.

- [x] T020 [US3] Implement the fail-fast matrix + exit codes (10–14) in `detect-broker.py` per contracts/detect-broker.md (empty/unwritable mount, malformed yaml, missing explicit path, client 0/>1, xtquant 0/>1) with specific messages.
- [ ] T021 [US3] On the NAS, run the fail-fast scenarios; confirm distinct messages, correct non-zero exit codes, and that no RDP/MCP port is left listening.

**Checkpoint**: fail-closed behavior verified.

## Phase 6: Polish & Cross-Cutting

- [x] T022 [P] Write `qmt-wine-rdp/docs/BROKER-PACK.md`: pack layout, `broker.yaml` schema, make-pack, switching, multi-instance, fail-fast reference.
- [ ] T023 [P] Update `qmt-wine-rdp/README.md` to the base-image + broker-pack model (replace the baked-image narrative).
- [ ] T024 Run `specs/001-broker-pack-base/quickstart.md` end-to-end on the NAS as the acceptance pass; record results.
- [ ] T025 Verify Success Criteria SC-001..SC-005 (swap < 10 min no build; ≤5-line broker.yaml; all fail-fast distinct; 2 instances concurrent; zero tracked-file changes on switch).

## Dependencies & Order

- Phase 1 → Phase 2 (foundational) → US1 (MVP) → US2 → US3 → Polish.
- US2 and US3 both extend `detect-broker.py` (T005); they share that file so are not mutually [P], but each is independently testable on top of the MVP.
- [P] tasks touch distinct files: T012, T018, T022, T023.

## MVP Scope

Foundational (T003–T010) + US1 (T011–T016): a broker-neutral base image plus a
mounted pack with an explicit `broker.yaml` that boots and is swappable without a
rebuild. Auto-detection (US2) and fail-fast hardening (US3) layer on next.
