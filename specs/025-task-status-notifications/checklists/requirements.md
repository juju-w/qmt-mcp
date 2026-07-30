# Specification Quality Checklist: Task Status Notifications

**Feature**: `specs/025-task-status-notifications/spec.md`

- [x] CHK001 User value is described independently of implementation.
- [x] CHK002 Stable `notifications/tasks` is distinguished from removed
  `notifications/tasks/status`.
- [x] CHK003 Preferred `2026-07-28` and 2025/polling compatibility are explicit.
- [x] CHK004 Acknowledgement-first ordering and subscription-ID metadata are
  testable.
- [x] CHK005 Current snapshot and reconnect semantics avoid an implicit replay
  promise.
- [x] CHK006 Complete DetailedTask notification shapes cover input and every
  terminal state.
- [x] CHK007 Ownership, scope, unknown-ID, and expiry disclosure rules are
  explicit.
- [x] CHK008 Input count, ID size, stream count, and backlog bounds are
  identified.
- [x] CHK009 Slow consumers and disconnect cleanup cannot block task execution.
- [x] CHK010 Mixed standard subscription filters remain supported.
- [x] CHK011 qmtctl notification preference and polling fallback are
  independently testable.
- [x] CHK012 The official pending conformance scenario is not misrepresented as
  executable proof.
- [x] CHK013 Existing 019-024, OAuth, release, cross-build, and image gates
  remain required.
- [x] CHK014 No broker data, task arguments, input responses, or credentials
  enter notification state.
- [x] CHK015 Historical Resources/Registry placeholder scope is explicitly
  superseded rather than mixed into 025.
