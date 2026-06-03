# Implementation Plan: Deploy & Security Hardening

**Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

## Summary

Docs + example deploy config + a pure-shell pre-flight check. No image rebuild,
no code path change in the MCP. The MCP already enforces bearer auth (002); this
feature is about *not exposing it badly*.

## Technical Context

**Language/Version**: Markdown, a Caddyfile, a compose override, and POSIX-ish Bash.
**Testing**: `bash -n` on the script + a behavior run with sample env; YAML/compose
parse for the override; checklist review. No amd64/container run available here.
**Constraints**: never print secret values; fail closed on weak token; keep the
base image untouched (override-only).

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| III. Reproducible / Native | Override + examples in-repo; no hand-mutated image | PASS |
| V. Observable | Proxy health path uses `/livez` (005) | PASS |
| VI. Security by Default | Core of this feature: TLS, token strength, exposure | PASS |
| VII. Spec-Driven | Supersedes the stale "006 deploy" note in 005 | PASS |

## Project Structure

```text
qmt-wine-rdp/
├── docs/DEPLOY.md                 # NEW: threat model + topology + checklist
├── deploy/Caddyfile.example       # NEW: TLS termination -> MCP
├── docker-compose.tls.yml         # NEW: proxy override, MCP port internal
└── scripts/harden-check.sh        # NEW: pre-flight weak-config check
```

**Structure Decision**: Everything is additive and override-based so a dev `up`
still works unchanged; hardening is opt-in via the override + the check.

## Complexity Tracking

> Not required.
