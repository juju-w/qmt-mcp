<!-- SPECKIT START -->
Active feature: 012-database-persistence
Plan: specs/012-database-persistence/plan.md
Spec: specs/012-database-persistence/spec.md
Constitution: .specify/memory/constitution.md

Project: broker-agnostic QMT-MCP appliance. Base image (Wine wow64 + Windows
Python 3.12 + CJK fonts + fastmcp/uvicorn + MCP launcher + xrdp) is
broker-neutral; the QMT terminal + matching xtquant + broker.yaml are mounted
at /broker (read-write) as a "broker pack". Build/run on any native amd64 host; Apple Silicon only under emulation (Rosetta AVX limitation).
Includes: xtdata tools (003), instrument search (006), xttrade account queries (004), qmtctl CLI (007), PostgreSQL persistence (012).
<!-- SPECKIT END -->
