Read and follow `AGENT.md` before changing this repository. It is the canonical
source for architecture, security, testing, Conventional Commits, CI, and
release rules. The block below only carries the active Speckit context.

<!-- SPECKIT START -->
Active feature: specs/022-mcp-pagination-compression
Constitution: .specify/memory/constitution.md

Project: broker-agnostic QMT-MCP appliance. Base image (Wine wow64 + Windows
Python 3.12 + CJK fonts + official MCP SDK/uvicorn + MCP launcher + xrdp) is
broker-neutral; the QMT terminal + matching xtquant + broker.yaml are mounted
at /broker (read-write) as a "broker pack". Build/run on any native amd64 host; Apple Silicon only under emulation (Rosetta AVX limitation).
Includes: xtdata tools (003), instrument search (006), xttrade account queries (004), qmtctl CLI (007), PostgreSQL persistence (012), quote subscription cache (013), portfolio risk analysis (014), option/volatility data (015), reference data (016), custom sector management (017), formula/factor runtime (018).
<!-- SPECKIT END -->
