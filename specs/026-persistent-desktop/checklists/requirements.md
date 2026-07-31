# Specification Quality Checklist: Secure Persistent Desktop

**Purpose**: Validate the specification before implementation.

- [x] Scope separates Linux/RDP login from QMT broker login.
- [x] Human-only brokerage authentication is explicit.
- [x] VNC/noVNC and dual-display modes are explicitly out of scope.
- [x] Persistent and manual user journeys are independently testable.
- [x] Current production observations contain no address, account, or secret.
- [x] RDP security findings are prioritized and tied to requirements.
- [x] Network, TLS, certificate, password, privilege, channel, and session
      policies fail closed.
- [x] One-desktop/one-QMT/one-MCP invariants are measurable.
- [x] Native amd64 and real RDP-client acceptance is required.
- [x] Performance acceptance reflects the reason xrdp is preferred over VNC.
- [x] Compatibility and manual rollback are covered.
- [x] No implementation is authorized before the session-reattach POC passes.
- [x] Success criteria are measurable and include restart/race behavior.
- [x] Constitution principles III, V, VI, and VII are represented.

## Approval Gate

- [ ] Owner approves the preferred xrdp-only architecture.
- [ ] Native amd64 POC proves `xrdp-sesrun` reattachment with Windows App.
- [ ] Owner approves the breaking secure defaults: no default password and
      loopback-only RDP publishing.
