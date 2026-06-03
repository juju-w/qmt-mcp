<!-- SPECKIT START -->
Active feature: 002-mcp-server-core
Plan: specs/002-mcp-server-core/plan.md
Spec: specs/002-mcp-server-core/spec.md
Constitution: .specify/memory/constitution.md

Project: broker-agnostic QMT-MCP appliance. Base image (Wine wow64 + Windows
Python 3.12 + CJK fonts + fastmcp/uvicorn + MCP launcher + xrdp) is
broker-neutral; the QMT terminal + matching xtquant + broker.yaml are mounted
at /broker (read-write) as a "broker pack". Build/run on any native amd64 host; Apple Silicon only under emulation (Rosetta AVX limitation).
<!-- SPECKIT END -->
