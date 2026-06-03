# Implementation Plan: Broker-Agnostic Base Image + Broker Pack

**Branch**: `001-broker-pack-base` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-broker-pack-base/spec.md`

## Summary

Refactor the working prototype's single baked image into (1) a broker-neutral
**base image** and (2) a runtime-mounted **broker pack**. The base carries the
generic runtime only (Wine new-WoW64, Windows Python 3.12, CJK fonts, fastmcp+
uvicorn, MCP launcher/scripts, xrdp); it ships no QMT terminal and no xtquant.
A `detect-broker` step in the entrypoint reads `broker.yaml`, auto-detects the
client exe / userdata / xtquant from the mounted pack, fails fast on
missing/ambiguous inputs, and writes a resolved-config env file consumed by the
QMT launcher and the MCP launcher (the pack's xtquant goes on `sys.path` at
runtime — never copied into the image). Switching brokers = swapping the mounted
pack; the same image runs multiple broker instances.

## Technical Context

**Language/Version**: Bash (entrypoint/detect-broker/scripts); Windows Python 3.12 (Wine) for MCP/xtquant; Dockerfile. YAML for `broker.yaml`.

**Primary Dependencies**: Base image `scottyhardy/docker-wine:stable` (Wine 11 wow64); Python 3.12.10 (python.org installer, build-time); fastmcp + uvicorn (pip, build-time); p7zip-full + unrar (pack-making helper); xtquant + the QMT terminal (runtime, from pack — NOT in image).

**Storage**: Broker pack = host directory mounted read-write at `/broker` (QMT writes userdata/logs/config in-tree). No database.

**Testing**: Build-time smoke (fastmcp import + `qmt_mcp.filter_trade_tools()`, no xtquant needed); runtime contract checks (detect-broker fail-fast matrix; resolved-config correctness; RDP reachable; MCP `/sse` + token; xtquant imports from pack at runtime).

**Target Platform**: Native linux/amd64 host. Apple Silicon only under emulation (documented Rosetta AVX limitation).

**Project Type**: Containerized appliance (image + mounted data pack + scripts).

**Performance Goals**: Not latency-sensitive in this feature; base image build a few minutes; container start to RDP-ready in seconds; detect-broker resolution well under 5s.

**Constraints**: Base image MUST be broker-neutral (no terminal/xtquant/secrets). Pack mounted read-write. Fail closed. Reproducible from declared inputs; versions pinned.

**Scale/Scope**: One pack per running instance; multiple instances per host from one image. `broker.yaml` schema v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Broker-Agnostic Base | Base image contains no terminal/xtquant/broker data; broker supplied only via mounted pack; swap = no rebuild | PASS — Dockerfile drops setup_qmt + xtquant; pack mounted at `/broker` |
| II. Read-Only by Default | No trade tools enabled by default; `broker.yaml mcp.mode` defaults to `readonly` | PASS — schema default `readonly`; trade deferred |
| III. Reproducible / Native / Pinned | Build on amd64; versions pinned; repo is source of truth | PASS — pinned Python/base/deps; make-broker-pack documents pack creation; no hand-mutated container as truth |
| IV. Contract-First MCP | (MCP internals deferred to 002) — this feature only resolves config the MCP consumes | N/A this feature; resolved-config contract documented |
| V. Observable / Auditable / Readiness-Gated | Resolved config logged (no secrets); fail-fast surfaces problems | PASS — detect-broker logs resolution; runtime login-readiness is feature 005 |
| VI. Security by Default | No secrets in image/git; token via env; pack may hold session data (operator's) | PASS — secrets gitignored; `broker.yaml` carries no secrets |
| VII. Spec-Driven | This plan follows the approved spec; scope boundaries respected | PASS |

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-broker-pack-base/
├── plan.md              # This file
├── research.md          # Phase 0: key technical decisions
├── data-model.md        # Phase 1: broker.yaml schema + resolved-config entities
├── quickstart.md        # Phase 1: build base + make a pack + run + verify
├── contracts/
│   ├── broker.yaml.schema.md   # broker.yaml v1 contract
│   └── detect-broker.md        # entrypoint resolution + fail-fast contract
└── checklists/requirements.md  # spec quality checklist (done)
```

### Source Code (repository root)

```text
appliance/
├── Dockerfile                  # REFACTOR: broker-neutral base (no setup_qmt, no xtquant)
├── docker-compose.yml          # REFACTOR: mount /broker rw; per-instance port/token
├── .env                        # per-instance token (gitignored)
├── scripts/
│   ├── qmt-entrypoint.sh        # EDIT: run detect-broker before base entrypoint
│   ├── detect-broker.sh         # NEW: parse broker.yaml + auto-detect + fail-fast + write resolved env
│   ├── make-broker-pack.sh      # NEW: build a pack from setup_qmt.exe + xtquant rar
│   ├── start-qmt.sh             # EDIT: use resolved client/bin path
│   ├── start-mcp.sh             # EDIT: source resolved env; put pack xtquant on sys.path
│   └── verify-xtquant.sh        # EDIT: target the pack's xtquant
├── mcp/
│   └── qmt_mcp.py               # EDIT: read xtquant dir + mini path from resolved env
├── brokers/
│   ├── template/broker.yaml      # NEW: documented template
│   └── guangda-jinyangguang/broker.yaml  # NEW: example (光大金阳光)
└── docs/
    └── BROKER-PACK.md           # NEW: pack layout + broker.yaml + switching guide
```

**Structure Decision**: Keep everything under the existing `appliance/` app
directory (single deployable appliance). The broker pack lives OUTSIDE the image
(a host dir, e.g. `appliance/brokers/<id>/pack/`, gitignored) and is mounted
at `/broker`. `brokers/<id>/broker.yaml` examples are tracked; the heavy pack
contents are not.

## Complexity Tracking

> Not required — Constitution Check passed with no violations.
