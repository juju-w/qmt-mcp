# Requirements Checklist: MCP Tasks

**Purpose**: Validate specification quality before implementation.

**Created**: 2026-07-31

**Feature**: `specs/023-mcp-tasks/spec.md`

## Scope and acceptance

- [x] CHK001 Stable lifecycle and wire envelopes are explicit.
- [x] CHK002 Primary 2026 behavior and old-client synchronous fallback are
  independently testable.
- [x] CHK003 qmtctl wait, detach, sync, resume, update, and cancel are bounded.
- [x] CHK004 Success, application error, MCP error, cancellation, and restart
  outcomes are distinguished.
- [x] CHK005 024 multi-round input and 025 notifications remain separate.

## Safety and compatibility

- [x] CHK006 Tasks are bound to stable principals and original tool scopes.
- [x] CHK007 Unknown and unauthorized references are indistinguishable.
- [x] CHK008 Credentials, raw identity, and tool arguments are excluded from
  persistence.
- [x] CHK009 IDs, body/header parsing, TTL, retention, and polling are bounded.
- [x] CHK010 Static, OAuth, hybrid, modern, and legacy behavior is covered.
- [x] CHK011 Conformance fixture tools are production-gated.
- [x] CHK012 Stable error `-32021` is separated from unreleased draft changes.

## Verification

- [x] CHK013 Official non-MRTR Tasks conformance scenarios are named.
- [x] CHK014 Broker-free unit, integration, Go, cross-build, and image gates
  are retained.
- [x] CHK015 Documentation and recovery/operator behavior are required.
