# QMT-MCP Appliance Constitution

A containerized, broker-agnostic appliance that runs a Windows QMT/MiniQMT
terminal under Wine on native linux/amd64 and exposes its market-data and
account-query capabilities to AI agents over MCP — safely.

## Core Principles

### I. Broker-Agnostic Base — the terminal is the only variable (NON-NEGOTIABLE)
The base image MUST contain no broker-specific terminal or data. The QMT
terminal, its matching `xtquant`, and a `broker.yaml` are supplied at runtime as
a mounted **broker pack**. Switching brokers MUST require only swapping the
mounted pack — never an image rebuild, never a code change. Paths/exe names are
resolved by auto-detection plus `broker.yaml` overrides.

### II. Read-Only by Default; Trading is Opt-In and Guarded (NON-NEGOTIABLE)
The MCP exposes NO order/cancel/transfer/borrow/export tools unless trading is
explicitly enabled (`mcp.mode: trade`). When enabled, every write MUST be gated
by an account allowlist, refuse any account not on it, and emit an audit record.
Read-only is the default everywhere; an empty/invalid config yields read-only.

### III. Reproducible, Native, Pinned Builds
Images build on native amd64 from declared inputs only. Versions (Python,
xtquant, base image, MCP deps) are pinned. The repository — not a hand-mutated
container — is the single source of truth. Any artifact in a running container
must be reproducible from `git checkout` + a documented build.

### IV. Contract-First MCP — structured, validated, explicit surface
Tools are an explicit contract: typed inputs with validation, structured
Pydantic outputs (no raw `dict[str, Any]` passthrough of SDK objects), named
enums instead of magic numbers, and accurate docstrings (the agent's only spec).
The exposed tool set is allow-listed, never the accidental union of a dependency.

### V. Observable, Auditable, Readiness-Gated
A health endpoint reports liveness and the connection state of xtdata / trader /
subscribed accounts. The MCP serves immediately but trader-dependent tools only
go live once readiness is confirmed. Every tool invocation is logged
(timestamp, tool, account, args summary, outcome); trade calls are audited.

### VI. Security by Default
Secrets (tokens, credentials) are never baked into images and never committed.
Endpoints require a bearer token; trading credentials live only in the operator's
QMT login session, never in config or image. Network exposure is minimized
(token + reverse-proxy/TLS or tunnel; no raw trading endpoint on an open LAN).

### VII. Spec-Driven Delivery
No implementation without an approved spec. Each feature flows
spec → (clarify) → plan → tasks → implement, one feature at a time. Specs are
technology-agnostic on the "what"; the "how" lives in plans. Scope creep is
resolved by writing a new spec, not by widening an in-flight one.

## Security & Safety Requirements

- Default posture is read-only; trading requires deliberate, auditable opt-in.
- Account allowlist enforced server-side; the agent cannot widen it via args.
- Bearer-token auth on all MCP/HTTP surfaces; reject unauthenticated requests.
- No secrets in image layers, git history, or `broker.yaml`.
- Fail closed: on ambiguous config or missing readiness, deny rather than guess.

## Development Workflow & Quality Gates

- Constitution check precedes every plan; violations require explicit
  justification recorded in the plan's Complexity Tracking, or a redesign.
- Each feature lands as an independently testable slice with a smoke/contract
  test (e.g., import + tool-list + token + a no-broker tool) runnable in CI or
  in the Wine Python.
- Build-time smoke tests guard the image (Python, xtquant import, MCP filter).
- Changes to the broker-pack contract or the exposed tool surface are breaking
  changes and require a version bump and migration note.

## Governance

This constitution supersedes ad-hoc practice. Amendments are made by editing this
file with a version bump and a dated note; principles marked NON-NEGOTIABLE
require an explicit, recorded rationale to override. Plans and reviews MUST
verify compliance; unjustified complexity is rejected.

**Version**: 1.0.0 | **Ratified**: 2026-06-02 | **Last Amended**: 2026-06-02
