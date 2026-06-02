# Phase 0 Research: Broker-Agnostic Base + Broker Pack

All spec NEEDS CLARIFICATION were resolved during `/speckit-specify` (Q1, Q2).
The remaining decisions are technical and recorded below.

## D1 — Mount point and writability
- **Decision**: Broker pack mounted **read-write** at `/broker` (single tree).
- **Rationale**: Q2 — QMT writes `userdata_mini`, logs, `config_local`, `data`
  scattered through its own tree; redirecting is brittle. `userdata` is part of
  the pack. Read-only mounts fail fast.
- **Alternatives**: read-only terminal + separate writable userdata volume —
  rejected as impractical (writes are not confined to one subdir).

## D2 — xtquant supply and loading
- **Decision**: xtquant comes **only from the pack**; base image ships none.
  At runtime the pack's xtquant **parent directory** is prepended to the Wine
  Python `sys.path` (no copy into site-packages, no copy into the image).
- **Rationale**: Q1 — xtquant is version-coupled to the terminal; the pack is the
  only place that can guarantee a match, and this keeps the base broker-neutral.
  sys.path injection avoids mutating the immutable base prefix and works because
  the pack is read-write/importable.
- **Alternatives**: copy xtquant into the Wine site-packages at startup —
  rejected (mutates the prefix, slower, redundant with a mounted pack).

## D3 — Where detect-broker runs and what language
- **Decision**: `detect-broker` is a **Python 3 script run on the Linux side**
  (the container OS), invoked by `qmt-entrypoint.sh` before `exec`-ing the base
  entrypoint. Base image adds `python3` + `python3-yaml` (apt).
- **Rationale**: Robust YAML parsing and path logic; bash YAML parsing is
  fragile. `python3`/`python3-yaml` are generic, broker-neutral tooling.
  It runs before xrdp/user setup so failures abort the container cleanly.
- **Alternatives**: bash + grep/sed YAML — rejected (fragile, hard to validate).

## D4 — Auto-detection algorithm
- **Decision**:
  - **client**: `terminal.client` if set (must exist, else fail); else scan by a
    **priority-ordered** known-name list (`XtItClient.exe` first, then
    `XtMiniQmt.exe`). The first name with exactly one match wins; the top-priority
    name with >1 copies → fail; no name matching → fail listing candidates.
    (Real QMT trees ship several client-named exes — e.g. both `XtItClient.exe`
    and `XtMiniQmt.exe` in `bin.x64` — so a flat "any-match" scan is always
    ambiguous; the priority order resolves the canonical interactive client
    without guessing. `make-broker-pack` additionally pins the resolved client in
    the starter `broker.yaml` so packs are self-describing.)
  - **userdata**: `terminal.userdata` if set; else find a dir named
    `userdata_mini` (prefer one beside the client); zero is allowed (created on
    first login) but the parent must be writable; multiple → fail listing.
  - **xtquant**: `xtquant.path` if set; else find a dir named `xtquant`
    containing `__init__.py`; one → use its parent; zero → fail; multiple → fail.
- **Rationale**: explicit wins; ambiguity is never silently guessed (fail
  closed). A wrong explicit path fails rather than being "corrected".

## D5 — Resolved-config handoff
- **Decision**: detect-broker writes Windows (Wine) paths via `winepath -w` into
  a resolved env file (`/run/qmt/broker.env`, world-readable to wineuser, no
  secrets). The entrypoint folds the MCP-relevant keys into `/opt/qmt-mcp/mcp.env`
  (existing bridge). Keys: `QMT_BROKER_ID`, `QMT_CLIENT_WIN`, `QMT_BIN_DIR_WIN`,
  `QMT_USERDATA_WIN`, `QMT_XTQUANT_DIR_WIN`, `QMT_MCP_MODE`.
- **Rationale**: reuses the proven container-env → XFCE-session bridge; keeps
  one source of resolved truth for both `start-qmt.sh` and `qmt_mcp.py`.

## D6 — Making a broker pack
- **Decision**: `make-broker-pack.sh <setup_qmt.exe> <xtquant.rar> <out-dir>`
  extracts the NSIS installer with `7z` and the RAR5 xtquant with `unrar` into
  `<out-dir>` and drops a starter `broker.yaml`. This replaces the prototype's
  build-time download/extract.
- **Rationale**: pack creation is an operator-side, broker-specific step done
  once per environment; keeping it out of the image is the whole point.
- **Note**: RAR5 requires `unrar` (RARLAB); the container's old `7z`/`unar`
  cannot decode it (learned in the prototype).

## D7 — Multi-instance
- **Decision**: one running container per pack. Distinct `container_name`, host
  ports, token, and pack mount per instance via compose env interpolation
  (`.env` per instance / compose override). Full multi-tenant deployment
  ergonomics are deferred to feature 006.
- **Rationale**: the base image is already stateless w.r.t. broker; isolation is
  just separate mounts + ports.

## D8 — Build-time smoke test (base, no xtquant)
- **Decision**: keep `import fastmcp` + `qmt_mcp.filter_trade_tools()` (module
  imports need no xtquant); **remove** the `import xtquant` build check (xtquant
  is not in the base). xtquant import is validated at **runtime** against the pack.
- **Rationale**: build must not depend on a broker artifact (Principle I/III).
