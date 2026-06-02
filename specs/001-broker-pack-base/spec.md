# Feature Specification: Broker-Agnostic Base Image + Broker Pack

**Feature Branch**: `001-broker-pack-base`

**Created**: 2026-06-02

**Status**: Draft

**Input**: User description: "Broker-agnostic base image + broker pack mechanism. The base container provides only the generic broker-neutral runtime and contains NO broker-specific QMT terminal, xtquant, or account data. The terminal, a matching xtquant, and a broker.yaml are supplied at runtime as a mounted broker pack. The startup process reads broker.yaml (all fields optional), auto-detects anything omitted by scanning the pack, resolves paths, and fails fast with a clear message if the client or xtquant is missing. Switching brokers requires only swapping the mounted pack — never a rebuild — and multiple broker containers can run from the same base image."

## Clarifications

### Session 2026-06-02

- **Q1 — xtquant ownership / base fallback**: xtquant is provided **exclusively by the broker pack**. The base image contains NO xtquant. Rationale: the xtquant python API is version-coupled to the terminal build, so the pack is the only place that can guarantee a match; this also keeps the base strictly broker-neutral (Constitution I). If a pack lacks an importable xtquant, startup fails fast.
- **Q2 — mount layout for terminal-writable data**: the broker pack is mounted **read-write as a single tree**. QMT writes `userdata_mini`/logs/`config_local`/`data` throughout its own directory tree, so redirecting those to a separate volume is brittle; the whole pack is writable and `userdata` is considered part of the pack. Swapping brokers = swapping this directory.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Switch broker environment by swapping the pack (Priority: P1)

An operator who already runs the appliance for broker A wants to also/instead run
it for broker B. They prepare a broker B pack (broker B's extracted QMT terminal,
a matching xtquant, and a `broker.yaml`), point the deployment at it, and start a
container from the **same, unchanged base image**. The appliance comes up driving
broker B's terminal.

**Why this priority**: This is the entire reason the feature exists — "swap one
exe to switch QMT environments." If only this works, the project delivers its core
value.

**Independent Test**: With a prebuilt base image and two prepared packs, start a
container against pack A, confirm it resolves and launches broker A's client; stop
it, start against pack B with no image change, confirm it resolves broker B's
client. No `docker build` occurs between the two.

**Acceptance Scenarios**:

1. **Given** a base image with no broker terminal baked in and a valid broker pack mounted, **When** the container starts, **Then** the appliance resolves the pack's client executable, userdata path, and xtquant, and reaches a running QMT desktop reachable over RDP.
2. **Given** the appliance running against pack A, **When** the operator redeploys with pack B mounted and the same image tag, **Then** the appliance now drives broker B's client with no rebuild and no source change.
3. **Given** two prepared packs, **When** two containers are started from the same image with different packs, ports, and tokens, **Then** both run independently and concurrently.

---

### User Story 2 - First-time pack setup with minimal config (Priority: P2)

An operator prepares a brand-new broker pack for the first time. They drop the
broker's extracted QMT directory and a matching xtquant into a folder, write a
short `broker.yaml` (or none), and start the appliance. Auto-detection finds the
client, userdata path, and xtquant without the operator hand-specifying paths.

**Why this priority**: Low-friction onboarding is what makes "swap a pack" actually
easy; without auto-detection every new broker needs path archaeology.

**Independent Test**: Provide a pack with a standard layout and an empty/minimal
`broker.yaml`; confirm the appliance starts successfully using only auto-detected
values, and that an explicit `broker.yaml` override changes the resolved values.

**Acceptance Scenarios**:

1. **Given** a pack with a standard layout and no `broker.yaml`, **When** the container starts, **Then** the client, userdata path, and xtquant are auto-detected and the appliance starts.
2. **Given** a pack where auto-detection would pick the wrong client, **When** `broker.yaml` specifies the client path explicitly, **Then** the explicit value is used.
3. **Given** a `broker.yaml` with only `broker.id` set, **When** the container starts, **Then** all other values are auto-detected and the broker id appears in logs/identification.

---

### User Story 3 - Fail fast and clearly on a bad pack (Priority: P2)

An operator mounts an incomplete or wrong pack (missing client exe, missing
xtquant, ambiguous layout, or unreadable mount). The appliance refuses to start
silently-broken; it stops with a clear, actionable message naming what was missing
and where it looked.

**Why this priority**: A silently half-broken trading-adjacent appliance is worse
than one that won't start. Clear failure protects the operator and supports the
constitution's "fail closed" principle.

**Independent Test**: Start the appliance against (a) an empty mount, (b) a pack
with a client but no xtquant, (c) a pack with two candidate clients and no
`broker.yaml` override; confirm each exits non-zero with a distinct, specific
message and no partially-started services.

**Acceptance Scenarios**:

1. **Given** no pack mounted (or an empty mount), **When** the container starts, **Then** it exits with a message stating the broker pack mount point is empty and what is expected there.
2. **Given** a pack missing xtquant and `xtquant.source` is `pack`, **When** the container starts, **Then** it exits with a message that xtquant was not found in the pack and how to supply it.
3. **Given** a pack with multiple plausible client executables and no override, **When** the container starts, **Then** it exits listing the candidates and asking the operator to disambiguate via `broker.yaml`.

---

### Edge Cases

- Pack mounted read-only → unsupported; the pack MUST be read-write because the terminal writes `userdata_mini`/logs/config into its own tree (Q2). A read-only mount fails fast.
- `broker.yaml` present but malformed (invalid YAML / unknown schema version) → fail fast with a parse error, do not fall back to guessing.
- `broker.yaml` points to a path that does not exist in the pack → fail fast (explicit override wins over auto-detect, so a wrong override must not be silently "corrected").
- Pack provides an xtquant whose CPython tag does not match the base image's Python → the startup xtquant import check surfaces a clear error and fails fast; deep version compatibility remains the operator's responsibility.
- Two containers mounting the **same** pack directory simultaneously (shared userdata) → unsupported; each running instance expects its own pack/userdata.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The base image MUST NOT contain any broker-specific QMT terminal, xtquant, or account/userdata. It contains only the broker-neutral runtime.
- **FR-002**: The appliance MUST accept a broker pack at a well-known mount point, containing the extracted QMT terminal, optionally a matching xtquant, and an optional `broker.yaml`.
- **FR-003**: On startup the appliance MUST read `broker.yaml` if present; every field MUST be optional, with auto-detection filling any omitted field.
- **FR-004**: The appliance MUST auto-detect the client executable, the userdata path, and the xtquant package by scanning the pack when not explicitly configured.
- **FR-005**: An explicit value in `broker.yaml` MUST take precedence over auto-detection, and a wrong explicit value MUST cause a fail-fast error rather than being silently overridden by detection.
- **FR-006**: The appliance MUST fail fast (exit non-zero, no partially-started services) with a specific, actionable message when the client executable cannot be resolved, when xtquant cannot be resolved per the configured source, when the pack mount is empty/unreadable, or when auto-detection is ambiguous and unresolved by `broker.yaml`.
- **FR-007**: Switching broker environments MUST require only swapping the mounted pack and its `broker.yaml` — never an image rebuild and never a source change.
- **FR-008**: The same base image MUST support running multiple concurrent appliance instances, each bound to a distinct pack, network port, and access token.
- **FR-009**: The `broker.yaml` schema MUST be documented and versioned; an unrecognized or unparseable `broker.yaml` MUST fail fast.
- **FR-010**: The resolved configuration (broker id, client path, userdata path, xtquant source/path) MUST be observable in startup logs for diagnosis, without leaking secrets.
- **FR-011**: The appliance MUST load xtquant **exclusively from the broker pack**; the base image MUST NOT contain xtquant. If the pack provides no importable xtquant, startup MUST fail fast with a specific message.
- **FR-012**: The broker pack MUST be mounted read-write as a single tree; the terminal persists its `userdata`/logs/config within that tree, and `userdata` is considered part of the pack. A read-only mount MUST fail fast.

### Key Entities *(include if feature involves data)*

- **Broker Pack**: A directory supplied at runtime containing one broker's extracted QMT terminal, optionally a matching xtquant package, and an optional `broker.yaml`. It is the unit operators swap to change environments.
- **broker.yaml**: The contract file describing a pack — broker identity, optional terminal paths (client exe, userdata), xtquant source/path, and MCP policy hints. All fields optional; documented and versioned.
- **Base Image**: The broker-neutral runtime artifact. Immutable across brokers; carries no broker terminal or data.
- **Resolved Configuration**: The effective settings after merging `broker.yaml` with auto-detection — what the appliance actually uses to launch and connect.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can bring up a second broker environment from an existing base image without any `docker build`, in under 10 minutes of pack preparation.
- **SC-002**: A pack with a standard layout starts successfully with a `broker.yaml` of 5 lines or fewer (or none), relying on auto-detection.
- **SC-003**: 100% of the defined bad-pack scenarios (empty mount, missing xtquant, ambiguous client) produce a distinct, specific failure message and a non-zero exit, with no RDP/MCP service left listening.
- **SC-004**: The same image tag runs at least two broker instances concurrently on one host without interference.
- **SC-005**: Switching brokers changes zero files tracked in the repository (only the mounted pack and its `broker.yaml` differ).

## Assumptions

- The operator obtains each broker's QMT terminal and a compatible xtquant themselves and places the xtquant inside the pack (the base image ships none); verifying deep version compatibility is the operator's responsibility (the startup import check only surfaces gross mismatches).
- The broker pack directory is writable by the container at runtime; operators back up/snapshot `userdata` as part of the pack.
- Login to the QMT terminal remains a manual, interactive step performed over RDP; runtime login-readiness detection and MCP exposure are covered by later features (002/005), not here.
- A broker pack corresponds to one terminal installation; one instance owns its pack/userdata exclusively at runtime.
- The base image continues to provide the RDP desktop for manual login, as validated in the prototype.
- Access token and per-instance network port are provided by the deployment layer (later feature); this feature only requires that they be per-instance.
- The prototype's proven stack (Wine new-WoW64 on native amd64, Windows Python 3.12, xtquant import, QMT extraction, RDP) is the starting point; this feature only relocates the broker terminal/xtquant from "baked" to "mounted".

## Dependencies

- Native linux/amd64 host (no Rosetta/QEMU), as established by the prototype.
- A prepared broker pack available on the host to mount.
