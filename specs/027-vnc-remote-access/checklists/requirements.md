# Requirements Checklist: VNC Remote Access

- [x] The user value is VNC credential persistence and broad/mobile clients,
  not merely unattended startup.
- [x] RDP and VNC are both first-class client options over one desktop.
- [x] Default deployments gain no VNC publication or process.
- [x] Separate Xvfb, duplicate XFCE/QMT/MCP, and unsafe `both` behavior are
  explicitly forbidden.
- [x] Password source, first-eight-character limitation, stdin conversion,
  redaction, file permissions, and fallback order are specified.
- [x] Loopback, LAN acknowledgement, raw transport, and no-public-internet
  boundaries are specified.
- [x] File transfer, commands, clipboard, reconnect, and failure-isolation
  behavior are specified.
- [x] Runtime status and singleton invariants are testable and secret-free.
- [x] PR #19's adopted ideas and replaced implementation choices are recorded.
- [x] Native VNC client, RDP/VNC alternation, restart, MCP/xtdata, CI, release,
  NAS rollout, and contributor-response acceptance are specified.
- [x] Broker pack, OAuth, MCP protocol, CLI, and read-only contracts remain
  unchanged.
