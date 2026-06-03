# Research: qmtctl CLI

## Decision: Go First

Use Go for the first CLI because the primary requirement is easy distribution.
Go's single-binary release story is simpler than Python packaging and faster to
iterate than Rust for this protocol-heavy utility.

## Decision: Thin Client Over MCP

Do not import xtquant, do not shell into containers for business calls, and do
not duplicate search/quote logic. The CLI calls the same MCP tools as AI
clients, preserving auth, audit, worker limits, and error envelopes.

## Alternatives

- Python + Typer: fastest to write, rejected for first release because users
  need a Python runtime and packaging story.
- Rust: good long-term option, deferred because MCP client behavior is still
  moving and Go is faster for v0.
- Node/Bun/Deno: workable but less attractive for small operational binaries.
