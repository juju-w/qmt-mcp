# Data Model: Secure Persistent Desktop

This feature adds no database schema. Runtime state is bounded and local to one
container generation; certificates are the only new persistent artifact.

## DesktopConfig

- `mode`: `manual` or `persistent`
- `user`: fixed configured desktop user, normally `wineuser`
- `geometry`: bootstrap width, height, and color depth
- `retry_limit`: bounded desktop bootstrap attempts
- `retry_backoff_s`: bounded retry schedule
- `password_source`: secret file path or compatibility environment source
- `certificate_mode`: generated-per-instance or operator-mounted
- `certificate_path` / `key_path`: runtime TLS files
- `clipboard_policy`: `none`, `text`, or explicit expanded policy
- `allow_lan`: explicit acknowledgement for non-loopback host publishing

Validation happens before any network listener starts. Secret values are never
serialized into status state.

## DesktopSessionIdentity

- `generation_id`: random identifier for one container start
- `session_id`: xrdp-sesman session identifier
- `display`: Xorg display number
- `uid`: desktop user ID
- `xorg_pid`, `xfce_pid`, `qmt_pid`, `mcp_supervisor_pid`
- `created_at`, `last_attached_at`, `last_detached_at`
- `state`: current `DesktopLifecycleState`

Only non-secret identifiers are written under `/run/qmt/desktop/` using atomic
replace and owner-only permissions.

## DesktopLifecycleState

Allowed states:

- `configuring`
- `starting_xrdp`
- `starting_session`
- `desktop_ready`
- `qmt_attention_required`
- `connector_ready`
- `degraded`
- `retrying`
- `failed`
- `stopping`

Transitions carry a stable reason code, attempt count, and timestamp. Human
messages must not include passwords, tokens, brokerage credentials, account
IDs, or raw QMT window text.

## SingletonLease

- `component`: `desktop`, `qmt`, or `mcp`
- `generation_id`
- `owner_pid`
- `acquired_at`
- `lock_file`: under `/run/qmt/desktop/`

Leases use kernel-backed file locking. A stale pidfile alone never proves that
an owner is alive, and a PID alone never proves process identity.

## RemoteAccessPolicy

- `host_bind`: loopback by default
- `container_port`: 3389
- `security_layer`: TLS only
- `minimum_tls`: TLS 1.2
- `certificate_fingerprint`: non-secret identity for diagnostics
- `allowed_group`: dedicated terminal-server group
- `root_login`: false
- `desktop_sudo`: false
- `channel_policy`: drives/files disabled by default
- `max_sessions`: one effective desktop session for the configured user

## Persisted Certificate Identity

- one private key and certificate per appliance instance
- generated after container creation or mounted by the operator
- persisted outside image layers across ordinary recreation
- private key readable only by the xrdp runtime identity
- fingerprint and expiry visible to the audit command

The private key is never copied to the broker pack unless the operator
explicitly selects that storage location.
