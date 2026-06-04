# Feature Specification: Custom Sector Management

**Status**: Draft
**Depends on**: 003 (sector read tools), 006 (instrument search), 007 (qmtctl
CLI), 010 (deploy hardening).

## Summary

Add an opt-in MCP tool family for managing QMT custom sectors/watchlists through
official xtdata sector mutation APIs. This is useful for operator-curated
universes, AI-generated candidate lists, and later subscription/cache workflows.

Unlike normal xtdata reads, this feature mutates local QMT state. Therefore it
is disabled by default, guarded by an explicit environment flag, restricted to
configured sector prefixes, and audited more strictly than read-only tools.

## User Scenarios

### US1 - Create an isolated MCP watchlist sector (P1)

**Acceptance**: Given sector writes are enabled and allowed prefix is `MCP/`,
when an operator creates `MCP/VIX candidates`, then QMT contains the sector and
the tool returns the exact created name or an idempotent already-exists result.

### US2 - Add/remove validated instruments safely (P1)

**Acceptance**: Given a managed sector and validated codes, when a user adds or
removes constituents, then only that sector is changed and all codes are checked
with existing instrument validation before xtdata mutation calls.

### US3 - Refuse unmanaged or broad destructive changes (P1)

**Acceptance**: Attempts to modify sectors outside allowed prefixes, delete
non-managed sectors, or reset broad built-in sectors are rejected before calling
xtdata.

### US4 - qmtctl workflow (P2)

**Acceptance**: `qmtctl sector create`, `qmtctl sector add`, `qmtctl sector remove`,
`qmtctl sector list-managed`, and `qmtctl sector delete` support readable output
and `--json`.

## Functional Requirements

- **FR-001**: Sector mutation tools MUST be disabled by default and require an
  explicit server-side flag such as `QMT_ENABLE_XTDATA_SECTOR_WRITE=1`.
- **FR-002**: Add MCP tools:
  `qmt_xtdata_sector_create_folder`, `qmt_xtdata_sector_create`,
  `qmt_xtdata_sector_add_codes`, `qmt_xtdata_sector_remove_codes`,
  `qmt_xtdata_sector_delete`, `qmt_xtdata_sector_reset`,
  and `qmt_xtdata_managed_sector_list`.
- **FR-003**: All mutation tools MUST restrict targets to configured allowed
  prefixes, defaulting to `MCP/` or `AI/`. Built-in sectors such as `沪深A股` MUST
  be read-only.
- **FR-004**: Code add/remove requests MUST validate QMT codes and max code
  count before calling xtdata.
- **FR-005**: Delete/reset MUST require `confirm=true` and MUST still be limited
  to managed prefixes.
- **FR-006**: Tools MUST return exact xtdata results plus normalized status:
  `created`, `updated`, `deleted`, `unchanged`, `refused`, or `partial`.
- **FR-007**: All mutation calls MUST be audited with sector name, operation,
  code count, prefix policy, and result status. Raw long code lists SHOULD be
  summarized in audit logs.
- **FR-008**: Health/capabilities MUST report sector-write disabled/enabled,
  allowed prefixes, and last mutation error without leaking secrets.
- **FR-009**: qmtctl MUST expose sector management commands and clearly surface
  disabled/refused responses.

## Safety Policy

- Default state: disabled.
- Allowed target names: must start with configured prefixes.
- Built-in sectors: never mutated.
- Deletes/resets: require `confirm=true`.
- Audit: mandatory for every mutation.
- No account/trading actions are exposed.

## Success Criteria

- **SC-001**: With sector writes disabled, every mutation tool returns disabled
  before calling xtdata.
- **SC-002**: With writes enabled, fake xtdata tests create a managed sector and
  add/remove validated codes.
- **SC-003**: Attempts to mutate sectors outside allowed prefixes are rejected.
- **SC-004**: Delete/reset require confirmation and remain prefix-limited.
- **SC-005**: qmtctl sector commands map to the MCP tools and support JSON output.

## Out of Scope

- Trading actions, account changes, or IPO subscription.
- Mutating built-in vendor sectors.
- Bulk full-market sector generation by default.
- Cross-device sector synchronization.

## Assumptions

- QMT sector mutation APIs change local QMT/xtdata state and may persist between
  restarts, so explicit opt-in and prefix limits are required.
- Some broker packs may omit create/delete/reset functions; capability diagnostics
  must be granular.
