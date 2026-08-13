---
name: deploying-qmt-mcp-appliance
description: Build, deploy, and verify the QMT-MCP appliance locally or on remote Linux, including static, OAuth JWT/JWKS, and hybrid endpoints. Use for first deployment, release artifacts, broker-pack or xtquant failures, exit codes 10-14, CRLF-broken images, silent `/livez`, and post-deploy validation.
---

# Deploying the QMT-MCP Appliance

First-deploy and remote-deploy failures, and how to verify the result. For steady-state
operations, tool tables, and `qmtctl` usage see **qmt-mcp-ops**.

This skill owns the Linux/NAS Docker topology. For a Windows x64 host with QMT
installed locally, use the native launcher Release instead: select/detect the
client in its Setup view, review resolved paths, and start it without Docker or
system Python/.NET. Do not apply Wine, broker-pack, RDP, or Compose diagnostics
to that topology.

## Core principle

Three things commonly break a first deploy: the **broker pack is incomplete**
(the QMT installer ships no `xtquant`), the **scripts have CRLF endings** (baked
into the image, not visible in `git diff`), and desktop lifecycle is misunderstood.
Recommended `persistent` mode starts MCP at boot; only rollback-compatible
`manual` mode waits for the first RDP login. Optional VNC is a client adapter to
that persistent display, not another headless QMT stack.

## Pre-flight

| Check | Command | Requirement |
|---|---|---|
| Native amd64 | `dpkg --print-architecture` | `amd64`. Apple Silicon = emulation, QMT hits Rosetta AVX |
| Disk | `df -h <build-dir> <pack-dir>` | **≥ 12 GB free** on the exact SSD/HDD mounts used for builds and broker data |
| Real disk mount | `findmnt -T <build-dir>` | Never use system `/tmp`, tmpfs, or ramfs for the build workspace, Docker data/cache, broker pack, or task store |
| Host tools | `command -v 7z unzip` | `make-broker-pack.sh` needs `7z`; `unzip` (zip) or `unrar` (RAR5) |

Docker's real usage may live under `/var/lib/containerd`, not `/var/lib/docker` — check
both when hunting space. On NAS hosts, place the workspace and Docker data root on
an SSD or HDD-backed persistent mount before building. `docker builder prune -af`
reclaims the cache after a build.

## Gotcha 1: CRLF from a Windows checkout kills the image

**Symptom:** container exits instantly; `/usr/bin/env: 'bash\r': No such file or directory`.

**Cause:** git `core.autocrlf=true` checks out `scripts/*.sh` with CRLF. `COPY scripts/`
bakes `#!/usr/bin/env bash\r` into the image. The repo's *stored blobs are LF*, so
`git diff` shows nothing and `git status` is clean.

```bash
# Detect (on the build host, before building)
head -1 appliance/scripts/qmt-entrypoint.sh | od -c | head -2   # look for \r \n

# Fix
find . -type f \( -name "*.sh" -o -name "*.py" \) -exec sed -i 's/\r$//' {} +
```

A `.gitattributes` forcing `eol=lf` on `*.sh`/`*.py`/`*.yml`/`*.yaml`/`Dockerfile`
prevents recurrence.

**You MUST rebuild after fixing.** The bad shebangs live in an image layer; fixing the
working tree changes nothing about an already-built image. Verify inside the image, not
on disk:

```bash
docker run --rm --entrypoint /bin/head <image> -1 /usr/local/bin/qmt-entrypoint.sh | od -c | head -2
```

Probe *after* `docker build` fully exports ("unpacking to ... done"). Probing mid-export
silently reads the previous image and you will "confirm" a fix that didn't happen.

## Gotcha 2: the QMT installer contains no xtquant

`make-broker-pack.sh` wants two inputs. Brokers ship the terminal installer; the
`xtquant` Python package is **separate and often not provided**. Verify before assuming:

```bash
7z l <setup_qmt.exe> | grep -iE 'xtquant|xtdata\.py'   # DLLs only = no Python package
```

Get a version-matched wheel from PyPI instead. **A wheel is a zip**, so the pack script
accepts it if renamed:

```bash
curl -fsSL -o xtquant.whl "https://pypi.tuna.tsinghua.edu.cn/packages/.../xtquant-250807.1.2-py3-none-any.whl"
sha256sum xtquant.whl                                   # verify against the PyPI index
cp xtquant.whl xtquant.zip                              # .whl is not a recognised extension
scripts/make-broker-pack.sh setup_qmt.exe xtquant.zip brokers/<id>/pack <broker-id>
```

The wheel must carry a `.pyd` matching the image's Python — `datacenter.cp312-win_amd64.pyd`
for Windows Python 3.12. Prove it imports under Wine rather than trusting the file listing:

```bash
docker exec -u wineuser <container> bash -lc \
  'cd /broker && xvfb-run -a wine "C:\\Python312\\python.exe" -c \
   "import sys; sys.path.insert(0, r\"Z:\\broker\"); import xtquant; from xtquant import xtdata; print(\"OK\")"'
```

Pass a script file rather than inline `-c` when nesting through `ssh` + `docker exec` —
backslashes get eaten and you get `failed to open "C:Python312python.exe"`.

## Gotcha 3: two client exes are not ambiguous

Real QMT trees ship both `XtItClient.exe` and `XtMiniQmt.exe`. This looks like exit 13
but isn't: `detect-broker` walks `CLIENT_NAMES` in priority order and the first name with
**exactly one** hit wins, so `XtItClient.exe` resolves. Pin it in `broker.yaml` anyway
for reproducibility. `userdata_mini` need not exist — it's created at login.

## Gotcha 4: desktop mode changes startup readiness

With `QMT_DESKTOP_MODE=persistent`, the entrypoint creates one Xorg/XFCE session
at boot. XFCE autostart launches QMT and MCP, so `/livez` becomes ready without
an attached RDP client and reconnects return to the same processes. Check
`/run/qmt/desktop/status.json` when startup stalls.

With rollback-compatible `manual`, QMT and MCP still launch only after the first
RDP desktop login. In that mode an initially unhealthy container is expected.

To verify the server headlessly without an RDP session:

```bash
docker exec -u wineuser -d <container> bash -lc \
  'mkdir -p /broker/logs && nohup /usr/local/bin/qmt-supervisor.sh > /broker/logs/supervisor-smoke.log 2>&1'
sleep 50 && docker exec <container> cat /broker/logs/supervisor-smoke.log   # expect "Application startup complete"
```

In either mode, `xtdata: degraded` + `无法连接xtquant服务` and
`xttrade: not_authorized` can persist until a human logs into the *broker
terminal* over RDP. Desktop startup and broker authentication are separate.

When retained credentials or Android access are needed, add
`docker-compose.vnc.yml`. It requires persistent mode and shares the exact Xorg,
QMT, and MCP identities with RDP. Keep port 15900 on loopback and tunnel it;
raw VNC is not encrypted, and classic authentication uses only the first eight
password characters. If `/run/qmt/desktop/status.json` reports
`vnc_state=degraded`, inspect x11vnc logs without restarting QMT/MCP first.

## Remote deploy from a Windows workstation

```bash
# rsync is often absent on both ends; tar-over-ssh needs nothing extra
tar czf - --exclude='.git' --exclude='__pycache__' --exclude='brokers/*/pack' \
    appliance cli skills VERSION | ssh <host> 'tar xzf - -C ~/project/qmt-mcp'
ssh <host> "cd ~/project/qmt-mcp && find . -type f \( -name '*.sh' -o -name '*.py' \) \
    -exec sed -i 's/\r\$//' {} +"        # ALWAYS strip CRLF after transferring
```

Upload the installer with `cat file | ssh host 'cat > dest'` and **compare `md5sum` on both
ends** — a truncated 240 MB upload produces confusing downstream failures.

Pull the base image separately before building. The pinned mirror
(`docker.1ms.run`) intermittently drops layers, surfacing as
`failed to compute cache key: short read: expected N bytes but got 0` — a *network*
error wearing a cache error's clothes. `docker pull` it, then build.

## Verification

Run `verify-mcp.sh` (in this skill directory) — handshake, auth enforcement, and tool
count in one shot:

```bash
# Public/remote endpoint: terminate TLS at the reverse proxy
read -r -s -p "QMT MCP token: " QMT_MCP_TOKEN; printf '\n'; export QMT_MCP_TOKEN
./verify-mcp.sh https://qmt.example.com

# Existing OAuth bearer (takes precedence over QMT_MCP_TOKEN)
read -r -s -p "QMT access token: " QMT_MCP_ACCESS_TOKEN; printf '\n'
export QMT_MCP_ACCESS_TOKEN
./verify-mcp.sh https://qmt.example.com

# Or keep MCP private and verify through an SSH tunnel
ssh -L 38765:127.0.0.1:38765 <host>
./verify-mcp.sh http://127.0.0.1:38765
unset QMT_MCP_ACCESS_TOKEN QMT_MCP_TOKEN
```

The verifier never accepts the bearer token as a positional argument, so it does not
land in shell history or process arguments. Remote plain HTTP is refused by default.
`QMT_MCP_ALLOW_INSECURE_HTTP=1` is an explicit escape hatch for an isolated, controlled
network. Set `QMT_MCP_MIN_TOOLS` only when intentionally deploying a reduced tool set;
the standard `full` appliance requires at least 37. For a server using
`QMT_MCP_TOOL_PROFILE=core`, `readonly`, `market`, `account`, or `custom`, set
the verifier threshold to the intended visible count and confirm the effective
policy with `qmtctl tools --json` plus `qmt_capabilities.tool_visibility`.
`qmtctl tools` follows all `tools/list` cursors, so the verifier and CLI see the
complete authorized catalog even when `QMT_MCP_LIST_PAGE_SIZE` is smaller than
the tool count. Eligible JSON responses use negotiated gzip by default; set
`QMT_MCP_GZIP_MIN_SIZE=0` only when the ingress owns compression.

Stable `2026-07-28` clients may also use durable Tasks. Keep
`QMT_MCP_TASK_STORE` on persistent real disk, never share one SQLite file among
multiple active MCP replicas, and include it in backups when detached task
recovery matters. Modern non-declaring clients remain synchronous.
Waiting tasks may expose standard MCP `inputRequests`; the prompt snapshot is
durable, but response values are in-process only. A restart marks the task
failed instead of replaying answers.
Stable task-aware clients may additionally receive current and changed state
through `subscriptions/listen` and `notifications/tasks`. This needs no new
ingress route: preserve long-lived POST/SSE responses on `/mcp`, disable proxy
buffering for them, and do not apply gzip to SSE. qmtctl falls back to
`tasks/get` if the stream cannot continue.

Use qmtctl for client-level discovery and smoke checks:

```bash
qmtctl version
qmtctl auth discover --json
qmtctl auth login \
  --client-id-metadata-url https://client.example.com/qmtctl.json \
  --scope 'qmt:read qmt:market'
qmtctl auth status
qmtctl health
qmtctl smoke --code 510300.SH
qmtctl --task-mode detach --json cache refresh --force
qmtctl task wait tsk_<id>
qmtctl --json task get tsk_<id>
```

`qmtctl auth discover` needs no token. Login uses Authorization Code + PKCE and
persists refresh rotation. MCP commands use an explicit access token first,
then a static token, then the saved per-resource OAuth session.
qmtctl's default task mode waits and prints the final tool result;
it prefers task notifications and transparently resumes polling after stream
loss. `--task-mode sync` exercises modern synchronous `tools/call`. If wait returns
`task_input_required`, review its request data and use explicit
`qmtctl task update`; never auto-accept a confirmation.

Manual probes worth knowing:

| Check | Expected |
|---|---|
| `curl -s <base>/livez` | `{"ok": true, "server": "live"}` |
| `curl -o /dev/null -w '%{http_code}' -X POST <base>/mcp -d '{}'` | `401` in every protected auth mode |
| `docker inspect <c> --format '{{.State.Health.Status}}'` | `healthy` |
| audit log `<pack>/logs/mcp-audit.jsonl` | one JSONL line per tool call |

MCP calls need `Accept: application/json, text/event-stream`. QMT-MCP 1.0 only
accepts `2026-07-28`: clients use `server/discover`, per-request metadata and
standard MCP headers without a session id. A modern POST response may be JSON
or SSE (`event: message\ndata: {...}`).

Audit timestamps carry Wine's TZ offset (e.g. `+0100`) while the container is
`Asia/Shanghai`. Same instant, different notation — not a misconfiguration.

`harden-check.sh` defaults to `appliance/.env` **relative to the repo root**. Run from
`appliance/` and it reports "not found" then fails on empty values it never read. Pass
the path: `./scripts/harden-check.sh .env`.

## Red flags

- Probing an image for a fix while `docker build` is still exporting
- Trusting `git status`/`git diff` to reveal CRLF (they can't)
- Concluding "deploy failed" from `unhealthy` + dead `/livez` before starting a session
- Assuming the broker installer includes `xtquant`
- Skipping the `md5sum` check on a large upload
- Chasing `xtdata: degraded` before the terminal has been logged into

## Common mistakes

| Mistake | Consequence |
|---|---|
| Fix CRLF, don't rebuild | Container keeps dying on baked-in `bash\r` |
| `docker build` without pre-pulling base | Spurious "cache key" failure mid-build |
| Pass `.whl` to `make-broker-pack.sh` | `unsupported xtquant archive` — copy to `.zip` |
| Nested inline `wine -c "..."` over ssh | `failed to open "C:Python312python.exe"` |
| Publish MCP on `0.0.0.0` over plain HTTP | Bearer token sniffable; use TLS proxy per `docs/DEPLOY.md` |

## Release artifacts and project rules

Each automatic GitHub Release publishes the appliance image, qmtctl archives,
and native Windows x64 launcher ZIP/setup with one `SHA256SUMS`. Prefer those
artifacts over rebuilding on an operator machine.

This skill owns deployment and validation only. Repository development,
Conventional Commits, CI gates, automatic SemVer, Docker layering, and cache
ownership are canonical in `AGENT.md`; detailed release operations are in
`docs/RELEASE.md`. Do not duplicate or override those policies here.
